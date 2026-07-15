"""HTTP client for the existing MiniMover control API."""

import json
import threading
import time
from urllib import request


class CarClient:
    def __init__(self, base_url="http://127.0.0.1:5000", timeout=3.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def execute(self, command, speed=35, duration=0.8):
        cmd = command["cmd"]
        if cmd == "rotate_left" or cmd == "spin":
            payload_cmd = "rotate_left"
        else:
            payload_cmd = cmd
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

    def execute_dance(self):
        """Execute a dance sequence: swing left-right 8 times (~10s).

        Runs in a background thread so the caller is not blocked.
        Returns the threading.Thread object.
        """
        def _dance():
            for _ in range(8):
                try:
                    self._send_move("left", speed=80, duration=0.6)
                except Exception:
                    pass
                time.sleep(0.65)
                try:
                    self._send_move("right", speed=80, duration=0.6)
                except Exception:
                    pass
                time.sleep(0.65)
        t = threading.Thread(target=_dance, daemon=True)
        t.start()
        return t

    def _send_move(self, cmd, speed=50, duration=0.5):
        """Low-level single move call without the command-mapping layer."""
        payload = {
            "cmd": cmd,
            "speed": max(10, min(int(speed), 100)),
            "duration": max(0.1, min(float(duration), 5.0)),
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
        return json.loads(raw)
