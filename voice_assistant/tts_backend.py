"""Queue-based, cancellable TTS playback backends."""

import json
import queue
import shlex
import subprocess
import threading
from urllib import request


class TtsBackend:
    def speak(self, text):
        raise NotImplementedError

    def stop(self):
        pass


class CarTtsBackend(TtsBackend):
    """Speak through the selected car's onboard speaker."""

    def __init__(self, car_url, lang="zh", timeout=10.0):
        from .car_audio_client import CarAudioClient
        self.car = CarAudioClient(car_url, timeout=timeout)
        self.lang = lang

    def speak(self, text):
        self.car.say(text, self.lang)

    def stop(self):
        self.car.stop_playback()

class HttpTtsBackend(TtsBackend):
    def __init__(self, base_url, api_key, voice="alloy", player_command="aplay -q -", timeout=30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.voice = voice
        self.player_command = player_command
        self.timeout = timeout
        self.queue = queue.Queue(maxsize=1)
        self.stop_event = threading.Event()
        self.player = None
        self.worker = threading.Thread(target=self._run, name="minimover-tts", daemon=True)
        self.worker.start()

    def speak(self, text):
        text = (text or "").strip()
        if not text:
            return
        try:
            self.queue.get_nowait()
        except queue.Empty:
            pass
        try:
            self.queue.put_nowait(text)
        except queue.Full:
            pass

    def _run(self):
        while not self.stop_event.is_set():
            try:
                text = self.queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                payload = {"model": "tts-1", "voice": self.voice, "input": text, "response_format": "wav"}
                req = request.Request(self.base_url + "/audio/speech", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json"}, method="POST")
                with request.urlopen(req, timeout=self.timeout) as response:
                    audio = response.read()
                self.player = subprocess.Popen(shlex.split(self.player_command), stdin=subprocess.PIPE)
                self.player.communicate(audio, timeout=self.timeout)
            except Exception:
                if self.player and self.player.poll() is None:
                    self.player.kill()
            finally:
                self.player = None

    def stop(self):
        self.stop_event.set()
        if self.player and self.player.poll() is None:
            self.player.kill()
        self.worker.join(timeout=1.0)
