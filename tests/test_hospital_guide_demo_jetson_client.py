import importlib

from voice_assistant import car_client_jetson as client


class _Poller:
    def __init__(self, payload):
        self._payload = payload
        self.calls = 0

    def poll_once(self):
        self.calls += 1
        return self._payload


def test_demo_mode_is_enabled_only_by_exact_one(monkeypatch):
    with monkeypatch.context() as env:
        env.setenv("MINIMOVER_HOSPITAL_GUIDE_DEMO_MODE", "true")
        importlib.reload(client)
        assert client.HOSPITAL_GUIDE_DEMO_MODE is False

        env.setenv("MINIMOVER_HOSPITAL_GUIDE_DEMO_MODE", "1")
        importlib.reload(client)
        assert client.HOSPITAL_GUIDE_DEMO_MODE is True

    importlib.reload(client)


def test_demo_welcome_poller_requires_both_guide_flags(monkeypatch):
    monkeypatch.setattr(client, "HOSPITAL_GUIDE_MODE", True)
    monkeypatch.setattr(client, "HOSPITAL_GUIDE_DEMO_MODE", False)
    assert client._demo_welcome_poller_enabled() is False

    monkeypatch.setattr(client, "HOSPITAL_GUIDE_MODE", False)
    monkeypatch.setattr(client, "HOSPITAL_GUIDE_DEMO_MODE", True)
    assert client._demo_welcome_poller_enabled() is False

    monkeypatch.setattr(client, "HOSPITAL_GUIDE_MODE", True)
    monkeypatch.setattr(client, "HOSPITAL_GUIDE_DEMO_MODE", True)
    assert client._demo_welcome_poller_enabled() is True


def test_demo_welcome_playback_mutes_capture_before_awaking_guide(monkeypatch):
    events = []
    poller = _Poller({"session_id": "session-1", "text": "欢迎您，请问需要去哪个科室？"})
    connected = iter([True, False])

    monkeypatch.setattr(client, "_guide_mark_asleep", lambda: events.append("asleep"))
    monkeypatch.setattr(
        client,
        "_speak",
        lambda text, capture_gate, send_control: events.append(
            ("speak", text, capture_gate, send_control)
        ),
    )
    monkeypatch.setattr(client, "_guide_mark_awake", lambda: events.append("awake"))

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
        "asleep",
        ("speak", "欢迎您，请问需要去哪个科室？", gate, sender),
        "awake",
    ]
    assert poller.calls == 1
    assert pauses == [0.5]
