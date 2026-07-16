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
        assert launcher._listener(port) is True
    assert launcher._listener(port) is False


def test_launchers_use_real_components_and_no_credentials():
    local = (ROOT / "scripts" / "start_hospital_guide_demo.py").read_text(encoding="utf-8")
    jetson = (ROOT / "scripts" / "start_hospital_guide_demo.sh").read_text(encoding="utf-8")
    assert "pc_asr_server.py" in local
    assert "voice_assistant/car_client_jetson.py" in jetson
    assert "voice_assistant/car_client.py" not in jetson
    assert "hospital-guide" in jetson
    assert jetson.count("MINIMOVER_HOSPITAL_GUIDE_DEMO_MODE=1") >= 2
    assert "MINIMOVER_HOSPITAL_GUIDE_MODE=1" in jetson
    assert "yahboom" not in local.lower()
    assert "sk-" not in local
    assert "MINIMOVER_SSH_PASSWORD" in local
