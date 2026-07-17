import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_hospital_guide_preflight.sh"
BASH = shutil.which("bash")


def test_preflight_script_allows_only_read_only_control_surfaces():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "--request" in source
    assert "GET" in source
    assert "/api/nav/stack/status" in source
    assert "/api/nav/pose" in source
    assert "/api/hospital-guide/demo/status" in source
    assert 'ros2 "$@"' in source
    assert "ros_query node list" in source
    assert "ros_query action list -t" in source
    assert "ros_query topic list -t" in source

    for forbidden in (
        "ros2 daemon", "ros2 launch", "ros2 run", "ros2 service call", "nav_stack.sh",
        "start_services.sh", "docker ", "--request POST", "--request PUT",
        "--request PATCH", "--request DELETE", "/api/nav/stack/start",
        "/api/nav/stack/stop", "/api/navigate", "/api/move",
        "/api/nav/initial_pose", "/api/nav/cancel",
    ):
        assert forbidden not in source


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _passing_bodies() -> dict[str, dict]:
    return {
        "stack": {"code": 0, "data": {"stack_ready": True}},
        "pose": {"code": 0, "data": {"valid": True, "frame_id": "map"}},
        "demo": {"code": 0, "data": {"session": {"phase": "READY"}}},
    }


def _run_preflight(
    tmp_path: Path,
    *,
    curl_bodies: dict[str, object] | None = None,
    ros_outputs: dict[str, str] | None = None,
    ros_available: bool = True,
    curl_exit_code: int = 0,
    api_base: str = "http://robot.example:5000",
    args: tuple[str, ...] = (),
):
    if os.name == "nt" or not BASH:
        pytest.skip("dynamic Bash preflight tests require a native POSIX Bash runtime")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl_log = tmp_path / "curl.log"
    ros_log = tmp_path / "ros.log"
    curl_bodies = _passing_bodies() if curl_bodies is None else curl_bodies
    ros_outputs = {
        "node": "/route_patrol\n",
        "action": "navigate_to_pose [nav2_msgs/action/NavigateToPose]\n",
        "topic": (
            "/map [nav_msgs/msg/OccupancyGrid]\n"
            "/amcl_pose [geometry_msgs/msg/PoseWithCovarianceStamped]\n"
            "/tf [tf2_msgs/msg/TFMessage]\n"
            "/odom [nav_msgs/msg/Odometry]\n"
            "/scan [sensor_msgs/msg/LaserScan]\n"
        ),
    } if ros_outputs is None else ros_outputs

    body_paths = {}
    for name in ("stack", "pose", "demo"):
        body_path = tmp_path / f"{name}.json"
        body = curl_bodies[name]
        body_path.write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
        body_paths[name] = body_path
    output_paths = {}
    for name in ("node", "action", "topic"):
        output_path = tmp_path / f"{name}.txt"
        output_path.write_text(ros_outputs[name], encoding="utf-8")
        output_paths[name] = output_path

    _write_executable(bin_dir / "curl", """#!/bin/bash
set -eu
printf '%s\\n' \"$*\" >> \"$CURL_LOG\"
out=''
url=''
while [ \"$#\" -gt 0 ]; do
  if [ \"$1\" = '--output' ]; then out=\"$2\"; shift 2; continue; fi
  url=\"$1\"
  shift
done
if [ \"$CURL_EXIT_CODE\" -ne 0 ]; then exit \"$CURL_EXIT_CODE\"; fi
case \"$url\" in
  \"$PREFLIGHT_API_BASE/api/nav/stack/status\") body=\"$CURL_STACK_BODY\" ;;
  \"$PREFLIGHT_API_BASE/api/nav/pose\") body=\"$CURL_POSE_BODY\" ;;
  \"$PREFLIGHT_API_BASE/api/hospital-guide/demo/status\") body=\"$CURL_DEMO_BODY\" ;;
  *) exit 97 ;;
esac
cp \"$body\" \"$out\"
""")
    if ros_available:
        _write_executable(bin_dir / "ros2", """#!/bin/bash
set -eu
printf '%s|%s\\n' \"${ROS_DOMAIN_ID-}\" \"$*\" >> \"$ROS_LOG\"
case \"$*\" in
  'node list') cat \"$ROS_NODE_OUTPUT\" ;;
  'action list -t') cat \"$ROS_ACTION_OUTPUT\" ;;
  'topic list -t') cat \"$ROS_TOPIC_OUTPUT\" ;;
  *) exit 98 ;;
esac
""")

    env = os.environ | {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "CURL_LOG": str(curl_log),
        "CURL_EXIT_CODE": str(curl_exit_code),
        "PREFLIGHT_API_BASE": api_base.rstrip("/"),
        "CURL_STACK_BODY": str(body_paths["stack"]),
        "CURL_POSE_BODY": str(body_paths["pose"]),
        "CURL_DEMO_BODY": str(body_paths["demo"]),
        "ROS_LOG": str(ros_log),
        "ROS_NODE_OUTPUT": str(output_paths["node"]),
        "ROS_ACTION_OUTPUT": str(output_paths["action"]),
        "ROS_TOPIC_OUTPUT": str(output_paths["topic"]),
    }
    completed = subprocess.run(
        [BASH, str(SCRIPT), "--api-base", api_base, *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed, curl_log.read_text(encoding="utf-8") if curl_log.exists() else "", (
        ros_log.read_text(encoding="utf-8") if ros_log.exists() else ""
    )


def test_preflight_uses_only_get_fixed_urls_and_anonymous_output(tmp_path):
    bodies = _passing_bodies()
    bodies["pose"]["data"] |= {"identity": "Alice", "transcript": "private"}
    completed, curl_log, ros_log = _run_preflight(
        tmp_path, curl_bodies=bodies, args=("--ros-domain", "30")
    )

    assert completed.returncode == 0
    assert "[PASS] api.nav_pose: valid=true frame_id=map" in completed.stdout
    assert "[PENDING] release_gate:" in completed.stdout
    assert "Alice" not in completed.stdout
    assert "private" not in completed.stdout
    assert curl_log.count("--request GET") == 3
    assert "/api/nav/stack/status" in curl_log
    assert "/api/nav/pose" in curl_log
    assert "/api/hospital-guide/demo/status" in curl_log
    assert "POST" not in curl_log and "start" not in curl_log and "stop" not in curl_log
    assert ros_log.splitlines() == [
        "30|node list", "30|action list -t", "30|topic list -t"
    ]


def test_preflight_fails_closed_for_bad_pose_and_missing_navigation_action(tmp_path):
    bodies = _passing_bodies()
    bodies["pose"] = {"code": 0, "data": {"valid": False, "frame_id": "odom"}}
    completed, _, _ = _run_preflight(
        tmp_path,
        curl_bodies=bodies,
        ros_outputs={"node": "/route_patrol\n", "action": "", "topic": "/map [nav_msgs/msg/OccupancyGrid]\n"},
    )

    assert completed.returncode == 1
    assert "[FAIL] api.nav_pose:" in completed.stdout
    assert "[FAIL] ros.navigate_to_pose:" in completed.stdout
    assert "[PENDING] release_gate:" in completed.stdout


@pytest.mark.parametrize(
    ("curl_bodies", "curl_exit_code", "expected"),
    [
        ({**_passing_bodies(), "pose": "not-json"}, 0, "[UNAVAILABLE] api.nav_pose:"),
        (_passing_bodies(), 22, "[UNAVAILABLE] api.nav_stack: GET unavailable"),
    ],
)
def test_preflight_reports_api_errors_without_echoing_payload(tmp_path, curl_bodies, curl_exit_code, expected):
    completed, _, _ = _run_preflight(
        tmp_path, curl_bodies=curl_bodies, curl_exit_code=curl_exit_code
    )

    assert completed.returncode == 1
    assert expected in completed.stdout
    assert "{\"code\"" not in completed.stdout


def test_preflight_fails_when_ros_discovery_is_unavailable(tmp_path):
    completed, _, ros_log = _run_preflight(
        tmp_path, curl_bodies=_passing_bodies(), ros_available=False
    )

    assert completed.returncode == 1
    assert "[UNAVAILABLE] ros.graph: ros2 command unavailable" in completed.stdout
    assert ros_log == ""


@pytest.mark.parametrize(
    ("api_base", "args"),
    [
        ("ftp://robot.example", ()),
        ("http://robot.example:5000", ("--api-base", "http://duplicate.example:5000")),
        ("http://robot.example:5000", ("--ros-domain", "-1")),
        ("http://robot.example:5000", ("--timeout-seconds", "0")),
        ("http://robot.example:5000", ("--timeout-seconds", "2", "--timeout-seconds", "3")),
        ("http://robot.example:5000", ("--unknown",)),
    ],
)
def test_preflight_rejects_invalid_or_duplicate_arguments_before_curl_runs(tmp_path, api_base, args):
    completed, curl_log, _ = _run_preflight(
        tmp_path, api_base=api_base, curl_bodies=_passing_bodies(), args=args
    )

    assert completed.returncode == 2
    assert "usage error" in completed.stderr
    assert curl_log == ""


def test_runbook_labels_preflight_as_read_only_and_not_a_release_gate():
    runbook = (ROOT / "docs" / "runbooks" / "five-minute-hospital-guide-demo.md").read_text(encoding="utf-8")

    assert "check_hospital_guide_preflight.sh" in runbook
    assert "\u53ea\u8bfb" in runbook
    assert "\u4e0d\u7b49\u4e8e\u5b9e\u8f66\u653e\u884c" in runbook
    assert "一名安全员" in runbook
    assert "硬件急停" in runbook
    assert "连续试跑三次" not in runbook
