"""Voice backends that use the car microphone and speaker over HTTP."""

import json
from urllib import request

from .asr_backend import AsrBackend
from .car_audio_client import CarAudioClient


def transcribe_wav(base_url, api_key, model, wav_data, timeout=30.0):
    boundary = "----MiniMoverVoice"
    body = (b"--" + boundary.encode() + b"\r\n"
        + b'Content-Disposition: form-data; name="file"; filename="speech.wav"\r\n'
        + b"Content-Type: audio/wav\r\n\r\n" + wav_data + b"\r\n"
        + b"--" + boundary.encode() + b"\r\n"
        + b'Content-Disposition: form-data; name="model"\r\n\r\n'
        + model.encode() + b"\r\n--" + boundary.encode() + b"--\r\n")
    req = request.Request(base_url.rstrip("/") + "/audio/transcriptions", data=body,
        headers={"Authorization": "Bearer " + api_key,
                 "Content-Type": "multipart/form-data; boundary=" + boundary}, method="POST")
    with request.urlopen(req, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    return str(result.get("text", "")).strip()


class RemoteWhisperBackend(AsrBackend):
    """Capture fixed-length utterances from the car and transcribe them remotely."""

    def __init__(self, car_url, whisper_url, api_key, model="whisper-1", duration=4.0, timeout=30.0):
        self.car = CarAudioClient(car_url, timeout=timeout)
        self.whisper_url = whisper_url
        self.api_key = api_key
        self.model = model
        self.duration = duration
        self.timeout = timeout

    def run(self, on_final, on_partial=None, stop_event=None):
        if not self.whisper_url or not self.api_key:
            raise RuntimeError("remote_whisper requires MINIMOVER_WHISPER_URL and MINIMOVER_API_KEY")
        while stop_event is None or not stop_event.is_set():
            on_partial and on_partial({"type": "listening", "source": "car"})
            _, wav_data = self.car.record(self.duration)
            if stop_event is not None and stop_event.is_set():
                break
            text = transcribe_wav(self.whisper_url, self.api_key, self.model, wav_data, self.timeout)
            if text:
                on_final({"type": "final_text", "text": text, "source": "remote_whisper"})
