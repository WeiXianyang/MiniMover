from voice_assistant.demo_session import DemoPhase, DemoSession


def test_start_replaces_session_and_enters_scanning():
    session = DemoSession()
    first = session.start()
    second = session.start()

    assert first["session_id"] != second["session_id"]
    assert second["phase"] == DemoPhase.SCANNING.value
    assert second["display_name"] is None


def test_welcome_claim_is_once_and_ack_must_match_current_session():
    session = DemoSession()
    started = session.start()

    assert session.set_welcome("王小明") is True
    assert session.claim_welcome() == {
        "session_id": started["session_id"],
        "text": "你好，王小明。请问您需要去哪个科室？",
    }
    assert session.claim_welcome() is None
    assert session.acknowledge_welcome("old") is False
    assert session.acknowledge_welcome(started["session_id"]) is True
    assert session.snapshot()["phase"] == "LISTENING"


def test_only_confirmation_then_navigation_then_arrival_is_valid():
    session = DemoSession()
    started = session.start()
    session.set_welcome(None)
    session.claim_welcome()
    session.acknowledge_welcome(started["session_id"])

    assert session.mark_navigation_started() is False
    assert session.mark_waiting_confirmation("internal_medicine") is True
    assert session.mark_navigation_started() is True
    assert session.mark_arrived() is True
    assert session.snapshot()["phase"] == "ARRIVED"
