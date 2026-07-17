from voice_assistant.demo_session_client import DemoWelcomePoller


def test_each_session_is_acknowledged_and_returned_once():
    claims = iter([
        {"session_id": "s1", "text": "\u4f60\u597d"},
        {"session_id": "s1", "text": "\u91cd\u590d"},
        None,
    ])
    calls = []
    poller = DemoWelcomePoller(
        claim=lambda: next(claims),
        ack=lambda ident: calls.append(ident) or True,
    )

    assert poller.poll_once() == {"session_id": "s1", "text": "\u4f60\u597d"}
    assert poller.poll_once() is None
    assert calls == ["s1"]


def test_listening_allowed_follows_server_demo_phase():
    phases = iter([
        {"session": {"phase": "SCANNING"}},
        {"session": {"phase": "LISTENING"}},
        {"session": {"phase": "WAITING_CONFIRMATION"}},
        {"session": {"phase": "NAVIGATING"}},
    ])
    poller = DemoWelcomePoller(status=lambda: next(phases))

    assert poller.listening_allowed() is False
    assert poller.listening_allowed() is True
    assert poller.listening_allowed() is True
    assert poller.listening_allowed() is False


def test_listening_allowed_is_unknown_when_status_cannot_be_read():
    poller = DemoWelcomePoller(status=lambda: None)

    assert poller.listening_allowed() is None
