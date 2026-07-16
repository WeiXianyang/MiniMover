"""Atomic, privacy-bounded runtime telemetry for the hospital guide console."""

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path


_DEFAULT_NAVIGATION = {
    "requested": False,
    "status": "not_requested",
    "message": "尚未下发导航",
    "department": None,
}


def _now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _safe_text(value, limit=300):
    return str(value or "").strip()[:limit]


def _safe_history(history):
    result = []
    for item in list(history or [])[-24:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = _safe_text(item.get("content"))
        if content:
            result.append({"role": role, "content": content})
    return result


def _safe_department(department):
    if not isinstance(department, dict):
        return None
    result = {
        key: _safe_text(department.get(key), 100)
        for key in ("id", "name", "floor")
        if _safe_text(department.get(key), 100)
    }
    if not result:
        return None
    result["navigation_enabled"] = bool(department.get("navigation_enabled", False))
    return result


def _safe_navigation(navigation):
    payload = dict(_DEFAULT_NAVIGATION)
    if isinstance(navigation, dict):
        payload["requested"] = bool(navigation.get("requested", False))
        payload["status"] = _safe_text(navigation.get("status"), 60) or "not_requested"
        payload["message"] = _safe_text(navigation.get("message"), 300) or "尚未下发导航"
        payload["department"] = _safe_department(navigation.get("department"))
    return payload


def default_snapshot():
    return {
        "schema_version": 1,
        "updated_at": None,
        "session": {"state": "IDLE", "pending_department": None},
        "memory": [],
        "knowledge": {"evidence_count": 0},
        "navigation": dict(_DEFAULT_NAVIGATION),
        "events": [],
    }


class HospitalGuideTelemetry:
    """Writes the console's bounded state snapshot without exposing map coordinates."""

    def __init__(self, path, max_events=50):
        self.path = Path(path)
        self.max_events = max(1, min(int(max_events), 100))
        self._lock = threading.Lock()
        existing = self.read()
        self._events = list(existing.get("events", []))[-self.max_events:]
        self._navigation = _safe_navigation(existing.get("navigation"))

    def publish(
        self,
        *,
        history,
        state,
        event_type,
        event_message,
        pending_department=None,
        evidence_count=0,
        navigation=None,
    ):
        with self._lock:
            if navigation is not None:
                self._navigation = _safe_navigation(navigation)
            self._events.append({
                "type": _safe_text(event_type, 60) or "reply",
                "message": _safe_text(event_message),
                "at": _now_iso(),
            })
            self._events = self._events[-self.max_events:]
            snapshot = {
                "schema_version": 1,
                "updated_at": _now_iso(),
                "session": {
                    "state": _safe_text(state, 60) or "IDLE",
                    "pending_department": _safe_department(pending_department),
                },
                "memory": _safe_history(history),
                "knowledge": {"evidence_count": max(0, int(evidence_count or 0))},
                "navigation": dict(self._navigation),
                "events": list(self._events),
            }
            self._write(snapshot)
            return snapshot

    def reset(self):
        with self._lock:
            self._events = []
            self._navigation = dict(_DEFAULT_NAVIGATION)
            snapshot = default_snapshot()
            snapshot["updated_at"] = _now_iso()
            self._write(snapshot)
            return snapshot

    def read(self):
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            return default_snapshot()
        if not isinstance(payload, dict):
            return default_snapshot()
        snapshot = default_snapshot()
        snapshot["updated_at"] = payload.get("updated_at")
        session = payload.get("session") if isinstance(payload.get("session"), dict) else {}
        snapshot["session"] = {
            "state": _safe_text(session.get("state"), 60) or "IDLE",
            "pending_department": _safe_department(session.get("pending_department")),
        }
        snapshot["memory"] = _safe_history(payload.get("memory"))
        knowledge = payload.get("knowledge") if isinstance(payload.get("knowledge"), dict) else {}
        try:
            snapshot["knowledge"]["evidence_count"] = max(0, int(knowledge.get("evidence_count", 0)))
        except (TypeError, ValueError):
            pass
        snapshot["navigation"] = _safe_navigation(payload.get("navigation"))
        events = payload.get("events") if isinstance(payload.get("events"), list) else []
        snapshot["events"] = [
            {
                "type": _safe_text(item.get("type"), 60) or "reply",
                "message": _safe_text(item.get("message")),
                "at": _safe_text(item.get("at"), 60),
            }
            for item in events[-100:]
            if isinstance(item, dict)
        ]
        return snapshot

    def _write(self, snapshot):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_name(self.path.name + ".tmp")
        temporary_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temporary_path, self.path)
