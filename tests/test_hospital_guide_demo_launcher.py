import importlib.util
import socket
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

def test_demo_runtime_sync_is_dedicated_to_hospital_guide():
    assert launcher.DEMO_RUNTIME_FILES == (
        Path("scripts/start_hospital_guide_demo.sh"),
        Path("scripts/start_hospital_rgb_camera.sh"),
        Path("api_server.py"),
        Path("audio/icar_audio.py"),
        Path("hospital_guide_bridge.py"),
        Path("hospital_guide_console.py"),
        Path("hospital_guide_demo.py"),
        Path("face/recognition.py"),
        Path("face/routes.py"),
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
    assert "内科演示点已通过 Nav2 路径规划校验" in source
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

    jetson = (ROOT / "scripts" / "start_hospital_guide_demo.sh").read_text(encoding="utf-8")
    assert "start_hospital_rgb_camera.sh" in jetson
    assert jetson.index("start_hospital_rgb_camera.sh") < jetson.index("/api/face/snapshot")
