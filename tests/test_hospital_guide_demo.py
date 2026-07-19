from flask import Flask

from hospital_guide_demo import HospitalGuideDemoController, register_hospital_guide_demo


class RecordingBridge:
    def __init__(self):
        self.reset_calls = 0

    def reset(self):
        self.reset_calls += 1


def _camera_failure():
    raise RuntimeError("camera unavailable")


def test_camera_failure_falls_back_to_guest_after_timeout():
    bridge = RecordingBridge()
    controller = HospitalGuideDemoController(
        bridge=bridge,
        snapshot_fetcher=_camera_failure,
        recognizer=lambda _: ({}, 503),
        scan_timeout_s=0.0,
    )

    controller.start()
    controller.scan_once()

    assert bridge.reset_calls == 1
    assert controller.claim_welcome() == {
        "session_id": controller.status()["session_id"],
        "text": "\u4f60\u597d\uff0c\u8bbf\u5ba2\u3002\u8bf7\u95ee\u60a8\u9700\u8981\u53bb\u54ea\u4e2a\u79d1\u5ba4\uff1f",
    }


def test_navigation_event_outside_confirmation_is_rejected():
    controller = HospitalGuideDemoController(
        bridge=RecordingBridge(),
        snapshot_fetcher=_camera_failure,
        scan_timeout_s=60.0,
    )

    controller.start()

    assert controller.on_guide_event({
        "type": "navigation_started",
        "department_id": "internal_medicine",
    }) is False
    assert controller.status()["phase"] == "SCANNING"


def test_claim_absent_welcome_is_204_and_bad_ack_is_409():
    app = Flask(__name__)
    controller = HospitalGuideDemoController(
        bridge=RecordingBridge(),
        snapshot_fetcher=_camera_failure,
        scan_timeout_s=60.0,
    )
    register_hospital_guide_demo(app, controller)
    client = app.test_client()

    assert client.post("/api/hospital-guide/demo/claim-welcome").status_code == 204
    started = client.post("/api/hospital-guide/demo/start").get_json()["data"]
    payload = client.get("/api/hospital-guide/demo/status").get_json()["data"]
    assert payload["session"]["session_id"] == started["session_id"]
    assert "navigation" in payload
    assert client.post(
        "/api/hospital-guide/demo/ack-welcome",
        json={"session_id": started["session_id"]},
    ).status_code == 409


def test_arrival_transition_uses_real_navigation_evidence_only():
    controller = HospitalGuideDemoController(
        bridge=RecordingBridge(),
        navigation_status=lambda: {"arrived": False, "status": "ACTIVE"},
        snapshot_fetcher=_camera_failure,
        scan_timeout_s=60.0,
    )

    controller.start()
    controller._session.set_welcome(None)
    claim = controller.claim_welcome()
    controller.acknowledge_welcome(claim["session_id"])
    controller.on_guide_event({
        "type": "department_matched",
        "department_id": "internal_medicine",
    })
    controller.on_guide_event({
        "type": "navigation_started",
        "department_id": "internal_medicine",
    })

    assert controller.refresh_navigation() is False
    controller._navigation_status = lambda: {"arrived": True, "status": "SUCCEEDED"}
    assert controller.refresh_navigation() is True
    assert controller.status()["phase"] == "ARRIVED"


def test_terminal_navigation_failure_enters_recovery():
    controller = HospitalGuideDemoController(
        bridge=RecordingBridge(),
        navigation_status=lambda: {
            "arrived": False,
            "status": "FAILED",
            "message": "Nav2 did not reach the target",
        },
        snapshot_fetcher=_camera_failure,
        scan_timeout_s=60.0,
    )

    controller.start()
    controller._session.set_welcome(None)
    claim = controller.claim_welcome()
    controller.acknowledge_welcome(claim["session_id"])
    controller.on_guide_event({
        "type": "department_matched",
        "department_id": "internal_medicine",
    })
    controller.on_guide_event({
        "type": "navigation_started",
        "department_id": "internal_medicine",
    })

    assert controller.refresh_navigation() is False
    assert controller.status()["phase"] == "RECOVERY"
    assert controller.status()["recovery_reason"] == "Nav2 did not reach the target"


def test_status_route_publishes_arrival_after_real_navigation_evidence():
    navigation = {"arrived": False, "status": "ACTIVE", "message": "goal active"}
    controller = HospitalGuideDemoController(
        bridge=RecordingBridge(),
        navigation_status=lambda: dict(navigation),
        snapshot_fetcher=_camera_failure,
        scan_timeout_s=60.0,
    )
    app = Flask(__name__)
    register_hospital_guide_demo(app, controller)
    client = app.test_client()

    controller.start()
    controller._session.set_welcome(None)
    claim = controller.claim_welcome()
    controller.acknowledge_welcome(claim["session_id"])
    controller.on_guide_event({
        "type": "department_matched",
        "department_id": "internal_medicine",
    })
    controller.on_guide_event({
        "type": "navigation_started",
        "department_id": "internal_medicine",
    })
    navigation.update({"arrived": True, "status": "SUCCEEDED", "message": "goal succeeded"})

    payload = client.get("/api/hospital-guide/demo/status").get_json()["data"]

    assert payload["session"]["phase"] == "ARRIVED"
    assert payload["navigation"]["status"] == "SUCCEEDED"
    assert payload["navigation"]["arrived"] is True


def test_public_status_exposes_only_demo_session_and_navigation_evidence():
    controller = HospitalGuideDemoController(
        bridge=RecordingBridge(),
        navigation_status=lambda: {"status": "IDLE", "arrived": False},
    )

    status = controller.public_status()

    assert set(status) == {"session", "navigation"}
    assert status["session"]["phase"] == "READY"
    assert status["navigation"]["status"] == "IDLE"


def test_scanner_welcomes_two_distinct_people_once_in_one_session():
    recognitions = iter([
        ({"ok": True, "identity": "\u5f20\u4e09", "confidence": 0.99, "user": {"id": "101"}}, 200),
        ({"ok": True, "identity": "\u5f20\u4e09", "confidence": 0.99, "user": {"id": "101"}}, 200),
        ({"ok": True, "identity": "\u674e\u56db", "confidence": 0.99, "user": {"id": "202"}}, 200),
    ])
    controller = HospitalGuideDemoController(
        bridge=RecordingBridge(),
        snapshot_fetcher=lambda: b"image",
        recognizer=lambda _: next(recognitions),
        scan_timeout_s=60.0,
    )
    controller._start_scanner_locked = lambda _session_id: None

    started = controller.start()
    assert controller.scan_once() is True
    first = controller.claim_welcome()
    assert "\u5f20\u4e09" in first["text"]
    assert controller.acknowledge_welcome(started["session_id"]) is True

    assert controller.scan_once() is False
    assert controller.claim_welcome() is None
    assert controller.scan_once() is True
    second = controller.claim_welcome()
    assert second["session_id"] == started["session_id"]
    assert second["welcome_id"] != started["session_id"]
    assert "\u674e\u56db" in second["text"]
    assert controller.status()["display_name"] == "\u674e\u56db"


def test_reset_clears_face_deduplication():
    payload = {"ok": True, "identity": "\u5f20\u4e09", "confidence": 0.99, "user": {"id": "101"}}
    controller = HospitalGuideDemoController(
        bridge=RecordingBridge(),
        snapshot_fetcher=lambda: b"image",
        recognizer=lambda _: (payload, 200),
        scan_timeout_s=60.0,
    )
    controller._start_scanner_locked = lambda _session_id: None

    first = controller.start()
    assert controller.scan_once() is True
    controller.claim_welcome()
    controller.acknowledge_welcome(first["session_id"])
    assert controller.scan_once() is False

    second = controller.reset()
    assert controller.scan_once() is True
    welcome = controller.claim_welcome()
    assert welcome["session_id"] == second["session_id"]
    assert "\u5f20\u4e09" in welcome["text"]
