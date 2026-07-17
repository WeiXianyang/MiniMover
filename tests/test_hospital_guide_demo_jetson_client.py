import importlib
import json

from voice_assistant import car_client_jetson as client


class _Poller:
    def __init__(self, payload):
        self._payload = payload
        self.calls = 0

    def poll_once(self):
        self.calls += 1
        return self._payload


def test_resolve_mic_prefers_xfm_capture_device(monkeypatch):
    monkeypatch.delenv("MINIMOVER_MIC_DEVICE", raising=False)
    devices = [
        {"name": "USB Audio Device: - (hw:0,0)", "max_input_channels": 0},
        {"name": "XFM-DP-V0.0.18: USB Audio (hw:1,0)", "max_input_channels": 1},
        {"name": "NVIDIA Jetson Orin NX APE", "max_input_channels": 16},
    ]

    assert client._resolve_mic_device(devices) == 1


def test_resolve_mic_honors_explicit_device_name_hint(monkeypatch):
    monkeypatch.setenv("MINIMOVER_MIC_DEVICE", "conference mic")
    devices = [
        {"name": "XFM-DP-V0.0.18: USB Audio", "max_input_channels": 1},
        {"name": "USB Conference Mic", "max_input_channels": 1},
    ]

    assert client._resolve_mic_device(devices) == 1


def test_demo_mode_is_enabled_only_by_exact_one(monkeypatch):
    with monkeypatch.context() as env:
        env.setenv("MINIMOVER_HOSPITAL_GUIDE_DEMO_MODE", "true")
        importlib.reload(client)
        assert client.HOSPITAL_GUIDE_DEMO_MODE is False

        env.setenv("MINIMOVER_HOSPITAL_GUIDE_DEMO_MODE", "1")
        importlib.reload(client)
        assert client.HOSPITAL_GUIDE_DEMO_MODE is True

    importlib.reload(client)


def test_demo_welcome_poller_only_requires_demo_mode(monkeypatch):
    monkeypatch.setattr(client, "HOSPITAL_GUIDE_DEMO_MODE", False)
    assert client._demo_welcome_poller_enabled() is False

    monkeypatch.setattr(client, "HOSPITAL_GUIDE_DEMO_MODE", True)
    assert client._demo_welcome_poller_enabled() is True


def test_demo_welcome_playback_mutes_capture_before_enabling_listening(monkeypatch):
    events = []
    poller = _Poller({"session_id": "session-1", "text": "你好，王小明。请问您需要去哪个科室？"})
    connected = iter([True, False])

    monkeypatch.setattr(client, "_demo_stop_listening", lambda: events.append("stopped"))
    monkeypatch.setattr(
        client,
        "_speak",
        lambda text, capture_gate, send_control: events.append(
            ("speak", text, capture_gate, send_control)
        ),
    )
    monkeypatch.setattr(client, "_demo_start_listening", lambda: events.append("listening"))

    gate = object()
    sender = object()
    pauses = []
    client._demo_welcome_loop(
        poller,
        capture_gate=gate,
        send_control=sender,
        is_connected=lambda: next(connected),
        pause=pauses.append,
    )

    assert events == [
        "stopped",
        ("speak", "你好，王小明。请问您需要去哪个科室？", gate, sender),
        "listening",
    ]
    assert poller.calls == 1
    assert pauses == [0.5]


def test_demo_ignores_final_text_before_face_welcome(monkeypatch):
    monkeypatch.setattr(client, "HOSPITAL_GUIDE_DEMO_MODE", True)
    monkeypatch.setattr(client, "_demo_is_listening", lambda: False)
    started = []

    class _Thread:
        def __init__(self, *args, **kwargs):
            started.append((args, kwargs))

        def start(self):
            started.append("started")

    monkeypatch.setattr(client.threading, "Thread", _Thread)
    client._on_message(None, json.dumps({"type": "final_text", "text": "带我去内科"}))

    assert started == []


def test_asr_only_logs_final_text_without_starting_hospital_guide(monkeypatch):
    monkeypatch.setattr(client, "ASR_ONLY", True)
    started = []

    class _Thread:
        def __init__(self, *args, **kwargs):
            started.append((args, kwargs))

        def start(self):
            started.append("started")

    monkeypatch.setattr(client.threading, "Thread", _Thread)
    client._on_message(
        None,
        json.dumps({"type": "final_text", "text": "我想去内科"}),
    )

    assert started == []


class _StatusPoller:
    def __init__(self, allowed):
        self.allowed = allowed

    def poll_once(self):
        return None

    def listening_allowed(self):
        return self.allowed


def test_demo_welcome_loop_restores_listening_from_server_phase_after_reconnect(monkeypatch):
    events = []
    connected = iter([True, False])
    monkeypatch.setattr(client, "_demo_start_listening", lambda: events.append("listening"))
    monkeypatch.setattr(client, "_demo_stop_listening", lambda: events.append("stopped"))

    client._demo_welcome_loop(
        _StatusPoller(True),
        capture_gate=object(),
        send_control=object(),
        is_connected=lambda: next(connected),
        pause=lambda _seconds: None,
    )

    assert events == ["listening"]


def test_demo_welcome_loop_stops_listening_when_server_is_scanning(monkeypatch):
    events = []
    connected = iter([True, False])
    monkeypatch.setattr(client, "_demo_start_listening", lambda: events.append("listening"))
    monkeypatch.setattr(client, "_demo_stop_listening", lambda: events.append("stopped"))

    client._demo_welcome_loop(
        _StatusPoller(False),
        capture_gate=object(),
        send_control=object(),
        is_connected=lambda: next(connected),
        pause=lambda _seconds: None,
    )

    assert events == ["stopped"]


def test_arrival_announcement_requires_verified_nav2_arrival_and_is_once_per_session():
    client._announced_arrival_sessions.clear()
    verified = {
        "session": {
            "session_id": "session-arrived",
            "phase": "ARRIVED",
            "department_id": "internal_medicine",
        },
        "navigation": {"status": "SUCCEEDED", "arrived": True},
    }

    assert client._claim_demo_arrival_announcement(verified) == "已到达内科，请注意脚下。"
    assert client._claim_demo_arrival_announcement(verified) is None

    client._announced_arrival_sessions.clear()
    for navigation in (
        {"status": "ACTIVE", "arrived": True},
        {"status": "SUCCEEDED", "arrived": False},
    ):
        payload = {**verified, "navigation": navigation}
        assert client._claim_demo_arrival_announcement(payload) is None


def test_demo_welcome_loop_speaks_only_verified_arrival(monkeypatch):
    client._announced_arrival_sessions.clear()
    events = []
    connected = iter([True, False])

    class _ArrivalPoller:
        def poll_once(self):
            return None

        def read_status(self):
            return {
                "session": {
                    "session_id": "session-arrived",
                    "phase": "ARRIVED",
                    "department_id": "internal_medicine",
                },
                "navigation": {"status": "SUCCEEDED", "arrived": True},
            }

        def listening_allowed(self, status=None):
            return False

    monkeypatch.setattr(client, "_demo_stop_listening", lambda: events.append("stopped"))
    monkeypatch.setattr(
        client,
        "_speak",
        lambda text, capture_gate, send_control: events.append(("speak", text)),
    )

    client._demo_welcome_loop(
        _ArrivalPoller(),
        capture_gate=object(),
        send_control=object(),
        is_connected=lambda: next(connected),
        pause=lambda _seconds: None,
    )

    assert events == ["stopped", ("speak", "已到达内科，请注意脚下。")]
