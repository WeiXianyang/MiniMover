"""Automatic face welcome and session-gated hospital guide demo APIs."""

import threading
from collections import deque
import time
from urllib import request

from flask import jsonify, request as flask_request

from face.recognition import identify_from_bytes
from voice_assistant.demo_session import DemoPhase, DemoSession


CAMERA_SNAPSHOT_URL = "http://127.0.0.1:8080/snapshot?topic=/camera/color/image_raw"
MIN_SNAPSHOT_BYTES = 500
INTERNAL_MEDICINE_ID = "internal_medicine"


def _default_navigation_status():
    from navigation.ros_bridge import demo_goal_status

    return demo_goal_status()


class HospitalGuideDemoController:
    """Coordinates a minimal, privacy-preserving five-minute guide session."""

    def __init__(
        self,
        *,
        bridge,
        session=None,
        snapshot_fetcher=None,
        recognizer=None,
        scan_timeout_s=8.0,
        confidence_threshold=0.90,
        scan_interval_s=0.5,
        navigation_status=None,
    ):
        self._bridge = bridge
        self._session = session or DemoSession()
        self._snapshot_fetcher = snapshot_fetcher or self._fetch_camera_snapshot
        self._recognizer = recognizer or identify_from_bytes
        self._scan_timeout_s = max(0.0, float(scan_timeout_s))
        self._confidence_threshold = min(1.0, max(0.0, float(confidence_threshold)))
        self._scan_interval_s = max(0.1, float(scan_interval_s))
        self._navigation_status = navigation_status or _default_navigation_status
        self._scanner_lock = threading.RLock()
        self._scanner_thread = None
        self._scanner_session_id = None
        self._replacement_session_id = None
        self._scan_started_at = None
        self._seen_identity_keys = set()
        self._welcome_queue = deque()
        self._claimed_extra_welcome = None
        self._welcome_sequence = 0

    def start(self):
        self._bridge.reset()
        with self._scanner_lock:
            started = self._session.start()
            self._scan_started_at = time.monotonic()
            self._seen_identity_keys.clear()
            self._welcome_queue.clear()
            self._claimed_extra_welcome = None
            self._welcome_sequence = 0
            self._start_scanner_locked(started["session_id"])
            return started

    def reset(self):
        return self.start()

    def status(self):
        return self._session.snapshot()

    def refresh_navigation(self):
        return self._apply_navigation_status(self._read_navigation_status())

    def public_status(self):
        navigation = self._read_navigation_status()
        self._apply_navigation_status(navigation)
        return {
            "session": self._session.snapshot(),
            "navigation": navigation,
        }

    def _read_navigation_status(self):
        try:
            result = self._navigation_status()
        except Exception as exc:
            return {
                "active": False,
                "arrived": False,
                "status": "FAILED",
                "message": "navigation status unavailable: %s" % exc,
            }
        if not isinstance(result, dict):
            return {
                "active": False,
                "arrived": False,
                "status": "FAILED",
                "message": "navigation status returned an invalid payload",
            }
        return dict(result)

    def _apply_navigation_status(self, result):
        if self._session.snapshot()["phase"] != DemoPhase.NAVIGATING.value:
            return False
        if result.get("arrived") is True:
            return self._session.mark_arrived()
        if result.get("status") in {"FAILED", "CANCELLED"}:
            self._session.recover(result.get("message", "navigation stopped"))
        return False

    def claim_welcome(self):
        with self._scanner_lock:
            initial = self._session.claim_welcome()
            if initial is not None:
                return initial
            if self._claimed_extra_welcome is not None or not self._welcome_queue:
                return None
            queued = self._welcome_queue.popleft()
            self._claimed_extra_welcome = queued
            self._session.record_identity(queued["display_name"])
            return {
                "session_id": queued["session_id"],
                "welcome_id": queued["welcome_id"],
                "text": queued["text"],
            }

    def acknowledge_welcome(self, session_id):
        with self._scanner_lock:
            if self._session.acknowledge_welcome(session_id):
                return True
            claimed = self._claimed_extra_welcome
            snapshot = self._session.snapshot()
            if (
                claimed is None
                or claimed["session_id"] != session_id
                or snapshot["session_id"] != session_id
            ):
                return False
            self._claimed_extra_welcome = None
            return True

    def scan_once(self, expected_session_id=None):
        """Try one face scan and enqueue each distinct identity once per session."""
        with self._scanner_lock:
            snapshot = self._session.snapshot()
            session_id = expected_session_id or snapshot["session_id"]
            if not self._scan_is_active(snapshot, session_id):
                return False

            display_name = None
            identity_key = None
            try:
                payload, status = self._recognizer(self._snapshot_fetcher())
                if self._is_confident_identity(payload, status):
                    display_name = payload["identity"].strip()
                    identity_key = self._identity_key(payload, display_name)
            except Exception:
                display_name = None
                identity_key = None

            current = self._session.snapshot()
            if not self._scan_is_active(current, session_id):
                return False
            if display_name and identity_key:
                if identity_key in self._seen_identity_keys:
                    return False
                self._seen_identity_keys.add(identity_key)
                if current["phase"] == DemoPhase.SCANNING.value:
                    return self._session.set_welcome(display_name)
                self._enqueue_welcome(session_id, display_name)
                return True
            if (
                current["phase"] == DemoPhase.SCANNING.value
                and self._scan_has_timed_out()
            ):
                return self._session.set_welcome(None)
            return False

    @staticmethod
    def _scan_is_active(snapshot, session_id):
        return (
            snapshot.get("session_id") == session_id
            and snapshot.get("phase") != DemoPhase.READY.value
        )

    @staticmethod
    def _identity_key(payload, display_name):
        user = payload.get("user")
        user_id = user.get("id") if isinstance(user, dict) else None
        if user_id is not None and str(user_id).strip():
            return "id:" + str(user_id).strip()
        return "name:" + display_name.casefold()

    def _enqueue_welcome(self, session_id, display_name):
        self._welcome_sequence += 1
        self._welcome_queue.append({
            "session_id": session_id,
            "welcome_id": "%s:%d" % (session_id, self._welcome_sequence),
            "display_name": display_name,
            "text": "\u4f60\u597d\uff0c%s\u3002\u6b22\u8fce\u6765\u5230\u533b\u9662\u3002" % display_name,
        })


    def on_guide_event(self, event):
        if not isinstance(event, dict) or event.get("department_id") != INTERNAL_MEDICINE_ID:
            return False
        event_type = event.get("type")
        if event_type == "department_matched":
            return self._session.mark_waiting_confirmation(INTERNAL_MEDICINE_ID)
        if event_type == "navigation_started":
            return self._session.mark_navigation_started()
        return False

    def _is_confident_identity(self, payload, status):
        if status != 200 or not isinstance(payload, dict) or not payload.get("ok"):
            return False
        identity = payload.get("identity")
        if not isinstance(identity, str) or not identity.strip():
            return False
        try:
            confidence = float(payload.get("confidence", 0))
        except (TypeError, ValueError):
            return False
        return confidence >= self._confidence_threshold

    def _scan_has_timed_out(self):
        if self._scan_started_at is None:
            return True
        return time.monotonic() - self._scan_started_at >= self._scan_timeout_s

    def _fetch_camera_snapshot(self):
        with request.urlopen(CAMERA_SNAPSHOT_URL, timeout=3) as response:
            image_bytes = response.read()
        if len(image_bytes) < MIN_SNAPSHOT_BYTES:
            raise RuntimeError("camera snapshot is too small")
        return image_bytes

    def _start_scanner_locked(self, session_id):
        if self._scanner_thread and self._scanner_thread.is_alive():
            if self._scanner_session_id != session_id:
                self._replacement_session_id = session_id
            return
        self._spawn_scanner_locked(session_id)

    def _spawn_scanner_locked(self, session_id):
        scanner = threading.Thread(
            target=self._scan_loop,
            args=(session_id,),
            daemon=True,
            name="hospital-guide-face-scanner",
        )
        self._scanner_thread = scanner
        self._scanner_session_id = session_id
        self._replacement_session_id = None
        scanner.start()

    def _scan_loop(self, session_id):
        try:
            while True:
                snapshot = self._session.snapshot()
                if not self._scan_is_active(snapshot, session_id):
                    return
                self.scan_once(expected_session_id=session_id)
                snapshot = self._session.snapshot()
                if not self._scan_is_active(snapshot, session_id):
                    return
                time.sleep(self._scan_interval_s)
        finally:
            with self._scanner_lock:
                if self._scanner_session_id != session_id:
                    return
                self._scanner_thread = None
                self._scanner_session_id = None
                replacement = self._replacement_session_id
                self._replacement_session_id = None
                snapshot = self._session.snapshot()
                if (
                    replacement
                    and snapshot["session_id"] == replacement
                    and snapshot["phase"] == DemoPhase.SCANNING.value
                ):
                    self._spawn_scanner_locked(replacement)


def register_hospital_guide_demo(app, controller):
    """Register demo-session endpoints on the existing Flask app."""

    @app.route("/api/hospital-guide/demo/start", methods=["POST"])
    def hospital_guide_demo_start():
        return jsonify({"code": 0, "data": controller.start()})

    @app.route("/api/hospital-guide/demo/reset", methods=["POST"])
    def hospital_guide_demo_reset():
        return jsonify({"code": 0, "data": controller.reset()})

    @app.route("/api/hospital-guide/demo/status", methods=["GET"])
    def hospital_guide_demo_status():
        return jsonify({"code": 0, "data": controller.public_status()})

    @app.route("/api/hospital-guide/demo/claim-welcome", methods=["POST"])
    def hospital_guide_demo_claim_welcome():
        welcome = controller.claim_welcome()
        if welcome is None:
            return "", 204
        return jsonify({"code": 0, "data": welcome})

    @app.route("/api/hospital-guide/demo/ack-welcome", methods=["POST"])
    def hospital_guide_demo_ack_welcome():
        payload = flask_request.get_json(silent=True)
        session_id = payload.get("session_id") if isinstance(payload, dict) else None
        if not controller.acknowledge_welcome(session_id):
            return jsonify({"code": 1, "msg": "welcome acknowledgement rejected"}), 409
        return jsonify({"code": 0, "data": controller.status()})

    return controller
