import importlib.util
import json
import socket
import sys
from pathlib import Path

import pytest

pytest.importorskip("paramiko")

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "start_hospital_guide_demo.py"

spec = importlib.util.spec_from_file_location("hospital_guide_demo_launcher", MODULE_PATH)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_listener_reports_real_tcp_listener():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        assert launcher._port_listening(port) is True
    assert launcher._port_listening(port) is False


def test_launchers_use_real_components_and_no_credentials():
    local = (ROOT / "scripts" / "start_hospital_guide_demo.py").read_text(encoding="utf-8")
    jetson = (ROOT / "scripts" / "start_hospital_guide_demo.sh").read_text(encoding="utf-8")
    assert "pc_asr_server.py" in local
    assert "voice_assistant/car_client_jetson.py" in jetson
    assert "voice_assistant/car_client.py" not in jetson
    assert "hospital-guide" in jetson
    assert "--restart-client" in jetson
    assert "seq 1 30" in jetson
    assert "asr_ready=0" in jetson
    assert "seq 1 15" in jetson
    assert "PC ASR is unreachable" in jetson
    assert ': > "$CAR_LOG"' in jetson
    assert jetson.index(': > "$CAR_LOG"') < jetson.index("nohup env")
    assert "yahboom" not in local.lower()
    assert "sk-" not in local
    assert "MINIMOVER_SSH_PASSWORD" in local

def test_local_voice_env_loads_missing_password_without_printing(tmp_path, capsys):
    env_path = tmp_path / ".env.voice"
    env_path.write_text(
        "# local launcher settings\n"
        "MINIMOVER_SSH_PASSWORD=factory-default\n"
        "MINIMOVER_ASR_LANGUAGE=auto\n",
        encoding="utf-8",
    )
    environment = {}

    loaded = launcher._load_local_env(env_path, environment=environment)

    assert environment["MINIMOVER_SSH_PASSWORD"] == "factory-default"
    assert environment["MINIMOVER_ASR_LANGUAGE"] == "auto"
    assert loaded == {"MINIMOVER_SSH_PASSWORD", "MINIMOVER_ASR_LANGUAGE"}
    assert capsys.readouterr().out == ""
    assert capsys.readouterr().err == ""


def test_local_voice_env_does_not_override_existing_environment(tmp_path):
    env_path = tmp_path / ".env.voice"
    env_path.write_text("MINIMOVER_SSH_PASSWORD=file-value\n", encoding="utf-8")
    environment = {"MINIMOVER_SSH_PASSWORD": "environment-value"}

    loaded = launcher._load_local_env(env_path, environment=environment)

    assert environment["MINIMOVER_SSH_PASSWORD"] == "environment-value"
    assert loaded == set()


def test_demo_runtime_sync_is_dedicated_to_hospital_guide():
    assert launcher.DEMO_RUNTIME_FILES == (
        Path("scripts/start_hospital_guide_demo.sh"),
        Path("scripts/start_hospital_rgb_camera.sh"),
        Path("scripts/check_hospital_guide_preflight.sh"),
        Path("api_server.py"),
        Path("audio/icar_audio.py"),
        Path("hospital_guide_bridge.py"),
        Path("hospital_guide_console.py"),
        Path("hospital_guide_demo.py"),
        Path("face/recognition.py"),
        Path("face/routes.py"),
        Path("face/store.py"),
        Path("navigation/config.py"),
        Path("navigation/department_markers.py"),
        Path("navigation/data/department_markers.json"),
        Path("navigation/patrol_page.py"),
        Path("navigation/ros_bridge.py"),
        Path("navigation/routes.py"),
        Path("voice_assistant/car_client_jetson.py"),
        Path("voice_assistant/audio_turn_safety.py"),
        Path("voice_assistant/demo_session.py"),
        Path("voice_assistant/demo_session_client.py"),
        Path("voice_assistant/hospital_guide.py"),
        Path("voice_assistant/hospital_guide_client.py"),
        Path("voice_assistant/data/hospital_guide_template.json"),
    )

    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "_listener(port)" not in source
    assert "_upload_demo_runtime" in source
    assert "--restart-client" in source
    jetson_path = ROOT / "scripts" / "start_hospital_guide_demo.sh"
    assert b"\r\n" not in jetson_path.read_bytes()
    jetson = jetson_path.read_text(encoding="utf-8")
    assert "MINIMOVER_HOSPITAL_GUIDE_DEMO_MODE=1" in jetson
    assert "MINIMOVER_NAV_OWNS_CHASSIS=1" in jetson
    assert "systemctl restart fireguard-api.service" in jetson
    assert "/api/hospital-guide/demo/start" in jetson


def test_launcher_reports_calibrated_internal_medicine_point_truthfully():
    source = Path("scripts/start_hospital_guide_demo.sh").read_text(encoding="utf-8")

    assert "当前未审核的科室点位保持禁用" not in source
    assert "内科新标定目标: (8.0, 3.0, 0.0)" in source
    assert "传感器健康检查通过前禁止释放急停" in source
    assert "已通过 Nav2 路径规划校验" not in source
    assert "实体移动前请清空场地" in source


def test_hospital_camera_launcher_uses_only_real_rgb_and_fails_closed():
    camera_script = ROOT / "scripts" / "start_hospital_rgb_camera.sh"
    source = camera_script.read_text(encoding="utf-8")

    assert b"\r\n" not in camera_script.read_bytes()
    assert "2bc5" in source and "050f" in source
    assert "usb_cam usb_cam_node_exe" in source
    assert "pgrep -f usb_cam_node_exe" in source
    assert "docker top \"$CAM_CONTAINER\" -eo cmd" not in source
    assert "pixel_format:=yuyv" in source
    assert "/camera/color/image_raw" in source
    assert 'rm -f "$snapshot_file"' in source
    assert "JPEG image data" in source
    assert "astro_pro_plus" not in source
    assert "astra_camera" not in source
    assert "mock" not in source.lower()

    restart = source.index('docker restart "$CAM_CONTAINER"')
    capability_probe = source.index('docker exec "$CAM_CONTAINER" v4l2-ctl')
    assert restart < capability_probe

    jetson = (ROOT / "scripts" / "start_hospital_guide_demo.sh").read_text(encoding="utf-8")
    assert "start_hospital_rgb_camera.sh" in jetson
    assert jetson.index("start_hospital_rgb_camera.sh") < jetson.index("/api/face/snapshot")


def _write_demo_target_fixture(root, navigation, marker):
    guide_path = root / "voice_assistant" / "data" / "hospital_guide_template.json"
    marker_path = root / "navigation" / "data" / "department_markers.json"
    guide_path.parent.mkdir(parents=True)
    marker_path.parent.mkdir(parents=True)
    guide_path.write_text(json.dumps({
        "departments": [{
            "id": "internal_medicine",
            "navigation": navigation,
        }],
    }), encoding="utf-8")
    marker_path.write_text(json.dumps({
        "markers": {"internal_medicine": marker},
    }), encoding="utf-8")


def test_launcher_validates_runtime_target_matches_display_marker(tmp_path):
    navigation = {"enabled": True, "x": 8.0, "y": 3.0, "theta": 0.0}
    _write_demo_target_fixture(tmp_path, navigation, {"x": 8.0, "y": 3.0})

    assert launcher._validate_demo_target_consistency(tmp_path) == (8.0, 3.0, 0.0)


def test_main_validates_demo_target_before_starting_services(monkeypatch):
    monkeypatch.setattr(sys, "argv", [str(MODULE_PATH)])
    monkeypatch.setattr(launcher, "_load_local_env", lambda *args, **kwargs: set())
    monkeypatch.setattr(launcher, "_local_ip_for", lambda host: "192.0.2.10")
    monkeypatch.setattr(
        launcher,
        "_validate_demo_target_consistency",
        lambda project_dir: (_ for _ in ()).throw(ValueError("unsafe demo target")),
    )
    monkeypatch.setattr(
        launcher,
        "_start_pc_asr",
        lambda *args, **kwargs: pytest.fail("ASR must not start before target validation"),
    )

    with pytest.raises(ValueError, match="unsafe demo target"):
        launcher.main()


def test_launcher_rejects_mismatched_runtime_target_and_display_marker(tmp_path):
    navigation = {"enabled": True, "x": 8.0, "y": 3.0, "theta": 0.0}
    _write_demo_target_fixture(tmp_path, navigation, {"x": 2.0, "y": 0.0})

    with pytest.raises(ValueError, match="target coordinates do not match"):
        launcher._validate_demo_target_consistency(tmp_path)
