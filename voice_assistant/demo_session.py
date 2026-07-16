"""Thread-safe, privacy-minimizing state for the five-minute hospital demo."""

from enum import Enum
from threading import RLock
from uuid import uuid4


class DemoPhase(str, Enum):
    READY = "READY"
    SCANNING = "SCANNING"
    WELCOME_PENDING = "WELCOME_PENDING"
    LISTENING = "LISTENING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    NAVIGATING = "NAVIGATING"
    ARRIVED = "ARRIVED"
    RECOVERY = "RECOVERY"


class DemoSession:
    """Keep only the public display name and state for one in-memory demo turn."""

    def __init__(self):
        self._lock = RLock()
        self._session_id = None
        self._phase = DemoPhase.READY
        self._display_name = None
        self._department_id = None
        self._welcome_claimed = False
        self._recovery_reason = None

    def start(self):
        with self._lock:
            self._session_id = uuid4().hex
            self._phase = DemoPhase.SCANNING
            self._display_name = None
            self._department_id = None
            self._welcome_claimed = False
            self._recovery_reason = None
            return self.snapshot()

    def set_welcome(self, display_name):
        with self._lock:
            if self._phase is not DemoPhase.SCANNING:
                return False
            self._display_name = str(display_name).strip() if display_name is not None else None
            self._phase = DemoPhase.WELCOME_PENDING
            self._welcome_claimed = False
            return True

    def claim_welcome(self):
        with self._lock:
            if self._phase is not DemoPhase.WELCOME_PENDING or self._welcome_claimed:
                return None
            self._welcome_claimed = True
            return {
                "session_id": self._session_id,
                "text": "你好，%s。请问您需要去哪个科室？" % (self._display_name or "访客"),
            }

    def acknowledge_welcome(self, session_id):
        with self._lock:
            if (
                self._phase is not DemoPhase.WELCOME_PENDING
                or not self._welcome_claimed
                or session_id != self._session_id
            ):
                return False
            self._phase = DemoPhase.LISTENING
            return True

    def mark_waiting_confirmation(self, department_id):
        with self._lock:
            if self._phase is not DemoPhase.LISTENING:
                return False
            self._department_id = str(department_id)
            self._phase = DemoPhase.WAITING_CONFIRMATION
            return True

    def mark_navigation_started(self):
        with self._lock:
            if self._phase is not DemoPhase.WAITING_CONFIRMATION:
                return False
            self._phase = DemoPhase.NAVIGATING
            return True

    def mark_arrived(self):
        with self._lock:
            if self._phase is not DemoPhase.NAVIGATING:
                return False
            self._phase = DemoPhase.ARRIVED
            return True

    def recover(self, reason):
        with self._lock:
            self._phase = DemoPhase.RECOVERY
            self._recovery_reason = str(reason).strip() or "unknown"
            return self.snapshot()

    def snapshot(self):
        with self._lock:
            return {
                "session_id": self._session_id,
                "phase": self._phase.value,
                "display_name": self._display_name,
                "department_id": self._department_id,
                "recovery_reason": self._recovery_reason,
            }
