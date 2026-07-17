"""Jetson-side polling client for one-time hospital demo welcomes."""

import json
from urllib import request


class DemoWelcomePoller:
    def __init__(
        self,
        base_url="http://127.0.0.1:5000",
        timeout=2.0,
        claim=None,
        ack=None,
        status=None,
    ):
        self.base_url = str(base_url or "http://127.0.0.1:5000").rstrip("/")
        self.timeout = float(timeout)
        self._seen = set()
        self._claim = claim or self._http_claim
        self._ack = ack or self._http_ack
        self._status = status or self._http_status

    def poll_once(self):
        try:
            payload = self._claim()
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        session_id = payload.get("session_id")
        text = payload.get("text")
        if not isinstance(session_id, str) or not session_id or session_id in self._seen:
            return None
        if not isinstance(text, str) or not text.strip():
            return None
        try:
            acknowledged = self._ack(session_id)
        except Exception:
            return None
        if not acknowledged:
            return None
        self._seen.add(session_id)
        return {"session_id": session_id, "text": text}


    def read_status(self):
        try:
            payload = self._status()
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def listening_allowed(self, payload=None):
        if payload is None:
            payload = self.read_status()
        if not isinstance(payload, dict):
            return None
        session = payload.get("session")
        if not isinstance(session, dict):
            return None
        phase = session.get("phase")
        if phase in {"LISTENING", "WAITING_CONFIRMATION"}:
            return True
        if isinstance(phase, str) and phase:
            return False
        return None

    def _http_status(self):
        req = request.Request(
            self.base_url + "/api/hospital-guide/demo/status",
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict) or payload.get("code") != 0:
            return None
        return payload.get("data")

    def _http_claim(self):
        req = request.Request(
            self.base_url + "/api/hospital-guide/demo/claim-welcome",
            data=b"",
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                if response.status == 204:
                    return None
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict) or payload.get("code") != 0:
            return None
        return payload.get("data")

    def _http_ack(self, session_id):
        body = json.dumps({"session_id": session_id}).encode("utf-8")
        req = request.Request(
            self.base_url + "/api/hospital-guide/demo/ack-welcome",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                return response.status == 200
        except Exception:
            return False
