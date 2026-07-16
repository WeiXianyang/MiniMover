# Read-Only Hospital Demo Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shell tool that makes only anonymous, read-only HTTP and ROS 2 discovery checks before the five-minute hospital-guide demo, without ever starting, stopping, cancelling, configuring, or moving the robot.

**Architecture:** `scripts/check_hospital_guide_preflight.sh` owns argument validation, fixed GET-only API probes, minimal JSON extraction, ROS graph discovery, and one explicit `release_gate=PENDING` line. `tests/test_hospital_guide_preflight_script.py` runs the script only in a POSIX Bash environment with temporary `curl` and `ros2` stubs; a source-contract test always checks that dangerous control verbs are absent. The runbook links the tool but retains human coordinate review and three physical test runs as mandatory release evidence.

**Tech Stack:** Bash, `curl`, Python 3 standard-library JSON parsing, ROS 2 CLI, pytest.

---

## File Structure

| Path | Responsibility |
| --- | --- |
| `scripts/check_hospital_guide_preflight.sh` | New, executable, read-only preflight CLI. It makes exactly three GET requests and runs only `ros2 ... list` discovery commands. |
| `tests/test_hospital_guide_preflight_script.py` | New pytest coverage using temporary executable stub commands; verifies URL/method allow-list, anonymized output, ROS command allow-list, failures, and argument validation. |
| `docs/runbooks/five-minute-hospital-guide-demo.md` | Add an optional preflight command before the existing field calibration procedure and reiterate that it cannot release navigation. |

## Safety Invariants to Preserve

1. The only network URLs are `/api/nav/stack/status`, `/api/nav/pose`, and `/api/hospital-guide/demo/status` appended to an approved `http://` or `https://` base URL.
2. Every HTTP call passes `--request GET`; no other HTTP method is implemented.
3. The only ROS commands are `ros2 node list`, `ros2 action list -t`, and `ros2 topic list -t`.
4. The script never invokes `ros2 launch`, `ros2 run`, `ros2 service call`, `nav_stack.sh`, Docker, start/stop/cancel endpoints, move endpoints, or initial-pose endpoints.
5. API responses are parsed locally but never printed in full. Output may include only HTTP availability, boolean/anonymous status, `pose.valid`, `pose.frame_id`, counts, and action/topic presence.
6. `release_gate` is always `PENDING`; exit code 0 can only mean the automatic read-only checks passed, never that field release was granted. Missing operational dependencies are an automatic-check failure (exit 1), not a release decision.

### Task 1: Write the preflight behavioral tests and stubs

**Files:**
- Create: `tests/test_hospital_guide_preflight_script.py`
- Create later in Task 2: `scripts/check_hospital_guide_preflight.sh`

- [ ] **Step 1: Add the failing source-contract test**

Create `tests/test_hospital_guide_preflight_script.py` with the following initial test. It must fail because the script does not yet exist.

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_hospital_guide_preflight.sh"


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
```

- [ ] **Step 2: Run the source-contract test and verify red**

Run:

```powershell
python -m pytest tests/test_hospital_guide_preflight_script.py::test_preflight_script_allows_only_read_only_control_surfaces -q
```

Expected: `FAIL` with `FileNotFoundError` for `scripts/check_hospital_guide_preflight.sh`.

- [ ] **Step 3: Add POSIX-only stub helpers and failing behavior tests**

Extend the same test file. Keep the source-contract test above unskipped. Dynamic shell tests should skip only when no native POSIX Bash is available, so Ubuntu/ROS CI executes them while Windows still performs the source contract.

```python
import json
import os
import shutil
import stat
import subprocess

import pytest

BASH = shutil.which("bash")


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
        ros_outputs={"node": "/route_patrol\\n", "action": "", "topic": "/map [nav_msgs/msg/OccupancyGrid]\\n"},
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
```

- [ ] **Step 4: Run the full new test file and verify red**

Run:

```powershell
python -m pytest tests/test_hospital_guide_preflight_script.py -q
```

Expected: the source-contract test fails because the script is absent. Dynamic tests may be skipped only on Windows because they require a native POSIX Bash runtime.

- [ ] **Step 5: Commit the test-first increment**

```powershell
git add tests/test_hospital_guide_preflight_script.py
git commit -m "test: define read-only preflight contract"
```

### Task 2: Implement the safe preflight shell script

**Files:**
- Create: `scripts/check_hospital_guide_preflight.sh`
- Test: `tests/test_hospital_guide_preflight_script.py`

- [ ] **Step 1: Create the CLI skeleton with strict argument handling**

Implement Bash functions `usage`, `usage_error`, `pass`, `fail`, and `unavailable`. Use `set -u` and a `mktemp -d` directory with `trap 'rm -rf "$TMP_DIR"' EXIT`. If `mktemp` fails, print a local `usage error` and exit `2`. Parse exactly `--api-base`, `--ros-domain`, `--timeout-seconds`, and `--help`; reject duplicates and unknown flags. Require a base matching `^https?://[^[:space:]]+$`, strip only trailing slashes, require `--ros-domain` to match `^[0-9]+$`, and require timeout to match `^[1-9][0-9]*$`.

The script’s initial structure must be equivalent to:

```bash
#!/usr/bin/env bash
set -u

API_BASE=''
ROS_DOMAIN=''
TIMEOUT_SECONDS=2
HAS_FAILURE=0
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

usage_error() { printf 'usage error: %s\n' "$1" >&2; exit 2; }
pass() { printf '[PASS] %s\n' "$1"; }
fail() { printf '[FAIL] %s\n' "$1"; HAS_FAILURE=1; }
unavailable() { printf '[UNAVAILABLE] %s\n' "$1"; HAS_FAILURE=1; }
```

- [ ] **Step 2: Add a fixed GET-only API probe and minimal JSON parsers**

Implement `probe_get(name, path, kind)`. Build the URL only as `"${API_BASE}${path}"`; do not accept a path from a caller or an environment variable. The only three call sites must be:

```bash
probe_get nav_stack /api/nav/stack/status stack
probe_get nav_pose /api/nav/pose pose
probe_get demo_status /api/hospital-guide/demo/status demo
```

Each call must use exactly this `curl` invocation shape; it may not use another method, another request helper, or a fallback URL:

```bash
curl --silent --show-error --fail --request GET \
  --connect-timeout "$TIMEOUT_SECONDS" --max-time "$TIMEOUT_SECONDS" \
  --output "$body_file" "$url"
```

On curl failure, call `unavailable "api.${name}: GET unavailable"` and continue. Never print curl response text. Parse the saved response only with `python3` and the standard library. Make the Python process return one tab-delimited safe summary, then map that summary to `pass`, `fail`, or `unavailable` in Bash:

```bash
summary=$(python3 - "$kind" "$body_file" <<'PY'
import json
import re
import sys

kind, filename = sys.argv[1:]
with open(filename, encoding="utf-8") as handle:
    payload = json.load(handle)
data = payload["data"]
if not isinstance(data, dict):
    raise ValueError("data must be an object")
if kind == "stack":
    ready = data.get("patrol_ready", data.get("stack_ready"))
    if not isinstance(ready, bool):
        raise ValueError("missing readiness boolean")
    print(f"stack\t{str(ready).lower()}")
elif kind == "pose":
    valid, frame_id = data.get("valid"), data.get("frame_id")
    if (
        not isinstance(valid, bool)
        or not isinstance(frame_id, str)
        or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_/-]{0,63}", frame_id)
    ):
        raise ValueError("missing or unsafe pose safety fields")
    print(f"pose\t{str(valid).lower()}\t{frame_id}")
elif kind == "demo":
    session = data.get("session")
    phase = session.get("phase") if isinstance(session, dict) else None
    if not isinstance(phase, str) or not re.fullmatch(r"[A-Z_]{1,48}", phase):
        raise ValueError("missing or unsafe anonymous phase")
    print(f"demo\t{phase}")
else:
    raise ValueError("unsupported parser")
PY
) || {
  unavailable "api.${name}: invalid anonymous JSON status"
  return
}
```

The Bash dispatch must print only these approved fields: stack `ready=true|false`; pose `valid=true|false frame_id=<frame_id>`; demo `phase=<phase>`. The parser must accept a frame ID only if it matches `[A-Za-z][A-Za-z0-9_/-]{0,63}` and a phase only if it matches `[A-Z_]{1,48}`; otherwise report `UNAVAILABLE` without echoing it. Treat `ready=false`, `valid=false`, or a non-`map` frame as `FAIL`; any missing `python3`, malformed JSON, or missing expected anonymous field is `UNAVAILABLE`. Do not attempt fallback commands or alternate API paths.

- [ ] **Step 3: Add ROS discovery with a fixed allow-list**

Add `ros_query()` so an optional domain applies only to the individual `ros2` invocation:

```bash
ros_query() {
  if [ -n "$ROS_DOMAIN" ]; then
    ROS_DOMAIN_ID="$ROS_DOMAIN" ros2 "$@"
  else
    ros2 "$@"
  fi
}
```

When `ros2` is unavailable, emit `[UNAVAILABLE] ros.graph: ros2 command unavailable`. Otherwise capture output from only these three calls, each in a separate temporary file:

```bash
ros_query node list
ros_query action list -t
ros_query topic list -t
```

Report only node count, whether output contains the exact action name `navigate_to_pose`, and which of the exact topic names `/map`, `/amcl_pose`, `/tf`, `/odom`, `/scan` occur. A missing `navigate_to_pose` or `/map` is a `FAIL`; discovery command errors are `UNAVAILABLE`. Do not call `ros2 daemon`, `ros2 launch`, `ros2 run`, or `ros2 service call`.

- [ ] **Step 4: Add the non-releasing summary and exit behavior**

After all probes, unconditionally print:

```bash
printf '[PENDING] release_gate: real-coordinate review and three test runs are still required\n'
```

Exit `1` if any `fail` or `unavailable` call occurred; otherwise exit `0`. A missing `curl`, `python3`, or `ros2` is reported as `UNAVAILABLE` and therefore exits `1`; exit `2` is reserved for command-line or local temporary-directory setup errors. Never use the `release_gate` line to alter the exit result. This preserves the distinction between automatic availability and field release.

- [ ] **Step 5: Run targeted tests and verify green**

Run:

```powershell
python -m pytest tests/test_hospital_guide_preflight_script.py -q
```

Expected: source contract passes; dynamic tests pass on native POSIX Bash and are skipped only where native Bash is unavailable. The passing stub must show exactly three GETs, the three fixed paths, and a ROS-domain value scoped to the three discovery commands.

Also run the shell syntax check in the Ubuntu ROS 2 workspace without sourcing or launching ROS:

```powershell
wsl.exe --distribution Ubuntu-22.04-ROS2 --exec /bin/bash --noprofile --norc -c "bash -n /mnt/e/MiniMover/.worktrees/five-minute-hospital-guide-demo-implementation/scripts/check_hospital_guide_preflight.sh"
```

Expected: exit code 0 and no output.

- [ ] **Step 6: Commit the implementation increment**

```powershell
git add scripts/check_hospital_guide_preflight.sh tests/test_hospital_guide_preflight_script.py
git commit -m "feat: add read-only hospital demo preflight"
```

### Task 3: Document the field use and preserve the manual release gate

**Files:**
- Modify: `docs/runbooks/five-minute-hospital-guide-demo.md`
- Test: `tests/test_hospital_guide_preflight_script.py`

- [ ] **Step 1: Add a failing documentation contract test**

Add this test to `tests/test_hospital_guide_preflight_script.py`:

```python
def test_runbook_labels_preflight_as_read_only_and_not_a_release_gate():
    runbook = (ROOT / "docs" / "runbooks" / "five-minute-hospital-guide-demo.md").read_text(encoding="utf-8")

    assert "check_hospital_guide_preflight.sh" in runbook
    assert "只读" in runbook
    assert "不等于实车放行" in runbook
    assert "连续试跑三次" in runbook
```

- [ ] **Step 2: Run the documentation contract test and verify red**

Run:

```powershell
python -m pytest tests/test_hospital_guide_preflight_script.py::test_runbook_labels_preflight_as_read_only_and_not_a_release_gate -q
```

Expected: `FAIL` because the runbook does not yet reference the new script.

- [ ] **Step 3: Add a preflight subsection before “内科点位标定与启用前放行”**

Insert the following content after the existing “演示前检查” list and before the coordinate-calibration heading. Keep the original calibration and three-run table unchanged.

```markdown
### 只读现场预检（不放行导航）

在车端 API 地址和 ROS 域已由现场操作员确认后，可运行：

```bash
bash scripts/check_hospital_guide_preflight.sh \
  --api-base http://127.0.0.1:5000 \
  --ros-domain 30
```

该工具只执行固定 API 的 `GET` 与 ROS 图发现；它不会启动、停止、取消导航或发送底盘控制。预检通过只说明自动检查项可见，**不等于实车放行**。仍须完成真实内科坐标记录、两名操作员独立复核以及固定起点连续试跑三次，才可启用 `internal_medicine`。
```

- [ ] **Step 4: Run the new script and runbook tests and verify green**

Run:

```powershell
python -m pytest tests/test_hospital_guide_preflight_script.py -q
```

Expected: all runnable new tests pass; native-Bash-only cases may be skipped on Windows.

- [ ] **Step 5: Commit the documentation increment**

```powershell
git add docs/runbooks/five-minute-hospital-guide-demo.md tests/test_hospital_guide_preflight_script.py
git commit -m "docs: add hospital demo preflight procedure"
```

### Task 4: Run regression and safety verification

**Files:**
- Verify only: `scripts/check_hospital_guide_preflight.sh`
- Verify only: `tests/test_hospital_guide_preflight_script.py`
- Verify only: `docs/runbooks/five-minute-hospital-guide-demo.md`

- [ ] **Step 1: Re-run preflight-specific tests after all changes**

```powershell
python -m pytest tests/test_hospital_guide_preflight_script.py -q
```

Expected: pass or documented Windows-only skip for POSIX shell behavior; no failure.

- [ ] **Step 2: Run relevant existing safety tests**

```powershell
python -m pytest -q tests/test_hospital_guide_demo_config.py tests/test_demo_navigation.py tests/test_navigation_pose.py tests/test_hospital_guide_demo_launcher.py
```

Expected: all tests pass, proving that navigation remains disabled by default, the arrival guard behavior remains intact, pose API behavior is unchanged, and the launcher remains correctly gated.

- [ ] **Step 3: Run static safety checks**

```powershell
$worktree = 'E:\MiniMover\.worktrees\five-minute-hospital-guide-demo-implementation'
git -C $worktree diff --check
wsl.exe --distribution Ubuntu-22.04-ROS2 --exec /bin/bash --noprofile --norc -c "bash -n /mnt/e/MiniMover/.worktrees/five-minute-hospital-guide-demo-implementation/scripts/check_hospital_guide_preflight.sh"
```

Expected: both commands exit 0. Inspect the final script with `rg` to confirm it contains no non-GET HTTP method and no ROS control command.

- [ ] **Step 4: Commit the verified regression state if any verification-only correction was needed**

If a verification-only correction changes files, stage only those specific files and use a narrowly scoped commit message. If no source changes were made during verification, do not create an empty commit.

## Plan Self-Review

- **Spec coverage:** Task 1 enforces the fixed API/ROS allow-lists, privacy output and parameter rules; Task 2 implements strict parsing, read-only HTTP, scoped ROS domain and permanent `PENDING` release gate; Task 3 teaches operators the tool is not a release mechanism; Task 4 verifies existing navigation safety gates are unaffected.
- **Scope:** No runtime web routes, ROS packages, Nav2 configuration, department coordinates, Docker configuration, face-recognition flow, or TTS flow are modified.
- **Consistency:** The script name, the three GET endpoints, output state `PENDING`, exit meanings, and the ROS allow-list are identical in the design, tests, implementation tasks and runbook task.
- **No placeholders:** Every code-change task names exact files, concrete commands, expected behavior and a commit boundary.
