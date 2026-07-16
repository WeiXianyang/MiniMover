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
