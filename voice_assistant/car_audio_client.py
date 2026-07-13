"""HTTP client for the car microphone and speaker APIs."""

import json
import time
from urllib import parse, request


class CarAudioClient:
    def __init__(self, base_url, timeout=10.0, poll_interval=0.1):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval

    def _request(self, path, method="GET", body=None, headers=None):
        req = request.Request(self.base_url + path, data=body, headers=headers or {}, method=method)
        with request.urlopen(req, timeout=self.timeout) as response:
            return response.read()

    def devices(self):
        return json.loads(self._request("/api/audio/devices").decode("utf-8"))

    def record(self, duration=4.0):
        body = json.dumps({"duration": duration}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        started = json.loads(self._request("/api/audio/record/start", "POST", body, headers).decode("utf-8"))
        if started.get("code") != 0:
            raise RuntimeError(started.get("msg", "car recording failed"))
        record_id = started["data"]["record_id"]
        deadline = time.monotonic() + duration + self.timeout
        while time.monotonic() < deadline:
            status = json.loads(self._request("/api/audio/record/status").decode("utf-8"))
            if status.get("data", {}).get("status") == "done":
                break
            time.sleep(self.poll_interval)
        else:
            raise TimeoutError("car recording did not finish")
        stopped = json.loads(self._request("/api/audio/record/stop", "POST").decode("utf-8"))
        if stopped.get("code") != 0:
            raise RuntimeError(stopped.get("msg", "car recording stop failed"))
        record_id = stopped["data"].get("record_id", record_id)
        return record_id, self._request("/api/audio/record/" + parse.quote(record_id, safe="") + ".wav")

    def say(self, text, lang="zh"):
        body = json.dumps({"text": text, "lang": lang}, ensure_ascii=False).encode("utf-8")
        result = json.loads(self._request("/api/audio/say", "POST", body, {"Content-Type": "application/json"}).decode("utf-8"))
        if result.get("code") != 0:
            raise RuntimeError(result.get("msg", "car TTS failed"))
        return result

    def stop_playback(self):
        return self._request("/api/audio/stop", "POST")
