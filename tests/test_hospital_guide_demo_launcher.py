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
    assert "yahboom" not in local.lower()
    assert "sk-" not in local
    assert "MINIMOVER_SSH_PASSWORD" in local

def test_demo_runtime_sync_is_dedicated_to_hospital_guide():
    assert launcher.DEMO_RUNTIME_FILES == (
        Path("scripts/start_hospital_guide_demo.sh"),
        Path("voice_assistant/car_client_jetson.py"),
        Path("voice_assistant/audio_turn_safety.py"),
        Path("voice_assistant/hospital_guide_client.py"),
    )

    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "_listener(port)" not in source
    assert "_upload_demo_runtime" in source
    assert "--restart-client" in source
