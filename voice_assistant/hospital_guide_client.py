"""HTTP client used by the Jetson WebSocket ASR process in hospital-guide mode."""

import json
from urllib import request


class HospitalGuideClient:
    def __init__(self, base_url="http://127.0.0.1:5000", timeout=8.0):
        self.base_url = str(base_url or "http://127.0.0.1:5000").rstrip("/")
        self.timeout = float(timeout)

    def process_final_text(self, text):
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")
        body = json.dumps({"text": text.strip()}, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            self.base_url + "/api/hospital-guide/turn",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("code") != 0:
            message = payload.get("msg") if isinstance(payload, dict) else "invalid hospital guide response"
            raise RuntimeError(str(message or "hospital guide request failed"))
        data = payload.get("data")
        reply = data.get("reply") if isinstance(data, dict) else None
        if not isinstance(reply, str) or not reply.strip():
            raise RuntimeError("hospital guide response has no reply")
        return reply.strip()
