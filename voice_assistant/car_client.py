"""HTTP client for the existing MiniMover control API."""

import json
from urllib import request


class CarClient:
    def __init__(self, base_url="http://127.0.0.1:5000", timeout=3.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def execute(self, command, speed=35, duration=0.8):
        cmd = command["cmd"]
        payload_cmd = "stop" if cmd == "stop" else ("rotate_left" if cmd == "spin" else cmd)
        payload = {
            "cmd": payload_cmd,
            "speed": max(10, min(int(speed), 100)),
            "duration": 0 if cmd == "stop" else max(0.1, min(float(duration), 5.0 if cmd != "spin" else 3.0)),
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.base_url + "/api/move",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout) as response:
            raw = response.read().decode("utf-8")
        result = json.loads(raw)
        if result.get("code") != 0:
            raise RuntimeError(result.get("msg", "car control failed"))
        return result
