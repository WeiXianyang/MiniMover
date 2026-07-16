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
    assert client.get("/api/hospital-guide/demo/status").get_json()["data"]["session_id"] == started["session_id"]
    assert client.post(
        "/api/hospital-guide/demo/ack-welcome",
        json={"session_id": started["session_id"]},
    ).status_code == 409
