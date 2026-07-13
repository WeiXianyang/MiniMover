"""Robust ASR backends adapted from MyMeeting's mature audio pipeline."""

import io
import json
import math
import queue
import threading
import time
import wave
from collections import deque
from urllib import request

SAMPLE_RATE = 16000
BLOCK_MS = 100
BLOCK_SAMPLES = SAMPLE_RATE * BLOCK_MS // 1000
PRE_ROLL_MS = 400
MIN_SPEECH_MS = 300
SILENCE_GAP_MS = 800
STREAMING_CHUNK_SIZE = [0, 10, 5]
STREAMING_CHUNK_SAMPLES = STREAMING_CHUNK_SIZE[1] * 960


class AsrBackend:
    def run(self, on_final, on_partial=None, stop_event=None):
        raise NotImplementedError


class _OnlineWorker:
    def __init__(self, model, on_result, max_queue=16):
        self.model = model
        self.on_result = on_result
        self.tasks = queue.Queue(maxsize=max_queue)
        self.thread = threading.Thread(target=self._run, name="minimover-funasr-online", daemon=True)
        self.stop_event = threading.Event()
        self.cache = {}
        self.thread.start()

    def submit(self, utterance_id, samples, is_final, chunk_index):
        try:
            self.tasks.put_nowait((utterance_id, samples, is_final, chunk_index))
            return True
        except queue.Full:
            try:
                self.tasks.get_nowait()
                self.tasks.put_nowait((utterance_id, samples, is_final, chunk_index))
                return True
            except queue.Empty:
                return False

    def _run(self):
        while not self.stop_event.is_set():
            try:
                utterance_id, samples, is_final, chunk_index = self.tasks.get(timeout=0.1)
            except queue.Empty:
                continue
            started = time.perf_counter()
            try:
                result = self.model.generate(
                    input=samples.astype("float32") / 32768.0,
                    cache=self.cache,
                    is_final=is_final,
                    chunk_size=STREAMING_CHUNK_SIZE,
                    encoder_chunk_look_back=4,
                    decoder_chunk_look_back=1,
                )
                text = _extract_text(result)
                self.on_result({
                    "kind": "final" if is_final else "partial",
                    "utterance_id": utterance_id,
                    "chunk_index": chunk_index,
                    "text": text,
                    "asr_ms": round((time.perf_counter() - started) * 1000, 1),
                })
                if is_final:
                    self.cache = {}
            except Exception as exc:
                self.on_result({"kind": "error", "utterance_id": utterance_id, "error": str(exc)})

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=1.0)


class FunAsrBackend(AsrBackend):
    """FunASR Paraformer 2-pass with pre-roll, dual VAD and async online ASR."""

    def __init__(self, sample_rate=SAMPLE_RATE, silence_ms=SILENCE_GAP_MS, vad_threshold=0.35):
        self.sample_rate = sample_rate
        self.block_samples = sample_rate * BLOCK_MS // 1000
        self.silence_ms = silence_ms
        self.vad_threshold = vad_threshold

    def run(self, on_final, on_partial=None, stop_event=None):
        try:
            import numpy as np
            import sounddevice as sd
            from funasr import AutoModel
            from silero_vad import get_speech_timestamps, load_silero_vad
        except ImportError as exc:
            raise RuntimeError("FunASR voice dependencies are missing; install requirements-voice.txt") from exc

        online_model = AutoModel(model="paraformer-zh-streaming", disable_update=True, disable_pbar=True)
        offline_model = AutoModel(
            model="paraformer-zh",
            vad_model="fsmn-vad",
            punc_model="ct-punc",
            disable_update=True,
            disable_pbar=True,
        )
        silero = load_silero_vad(onnx=True)
        results = queue.Queue()
        online = _OnlineWorker(online_model, results.put)
        audio_queue = queue.Queue(maxsize=64)
        pre_buffer = deque(maxlen=int(PRE_ROLL_MS * self.sample_rate / 1000))
        utterance = []
        speaking = False
        silence_blocks = 0
        utterance_id = 0
        chunk_index = 0
        noise_floor = 0.004
        last_partial_samples = 0

        def callback(indata, frames, time_info, status):
            del frames, time_info, status
            try:
                audio_queue.put_nowait(indata[:, 0].copy())
            except queue.Full:
                try:
                    audio_queue.get_nowait()
                    audio_queue.put_nowait(indata[:, 0].copy())
                except queue.Empty:
                    pass

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self.block_samples,
                callback=callback,
            ):
                while stop_event is None or not stop_event.is_set():
                    self._drain_results(results, on_partial, on_final)
                    try:
                        block = audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    block = np.asarray(block, dtype=np.int16).reshape(-1)
                    pre_buffer.extend(block.tolist())
                    level = _rms(block)
                    if not speaking and level < max(0.015, noise_floor * 3.0):
                        noise_floor = 0.95 * noise_floor + 0.05 * max(level, 0.0005)
                    snr_db = 20 * math.log10((level + 1e-8) / (noise_floor + 1e-8))
                    vad_window = np.asarray(pre_buffer, dtype=np.float32) / 32768.0
                    speech_ts = get_speech_timestamps(
                        vad_window,
                        silero,
                        threshold=self.vad_threshold,
                        return_seconds=False,
                        min_speech_duration_ms=MIN_SPEECH_MS,
                        min_silence_duration_ms=self.silence_ms,
                    )
                    vad_hit = bool(speech_ts)
                    voice_start = vad_hit and snr_db > 6.0 and level > max(0.003, noise_floor * 2.4)
                    voice_continue = vad_hit and snr_db > 3.0 and level > max(0.002, noise_floor * 1.45)
                    if not speaking and voice_start:
                        speaking = True
                        utterance = list(pre_buffer)
                        silence_blocks = 0
                        last_partial_samples = 0
                        chunk_index = 0
                        on_partial and on_partial({"type": "speech_start", "utterance_id": utterance_id})
                    elif speaking:
                        utterance.extend(block.tolist())
                        if voice_continue:
                            silence_blocks = 0
                            if len(utterance) - last_partial_samples >= STREAMING_CHUNK_SAMPLES:
                                start = max(0, len(utterance) - STREAMING_CHUNK_SAMPLES)
                                online.submit(utterance_id, np.asarray(utterance[start:], dtype=np.int16), False, chunk_index)
                                chunk_index += 1
                                last_partial_samples = len(utterance)
                        else:
                            silence_blocks += 1
                            if silence_blocks * BLOCK_MS >= self.silence_ms:
                                samples = np.asarray(utterance, dtype=np.int16)
                                if len(samples) >= int(self.sample_rate * MIN_SPEECH_MS / 1000):
                                    online.submit(utterance_id, samples, True, chunk_index)
                                    result = None
                                    try:
                                        result = offline_model.generate(
                                            input=samples.astype(np.float32) / 32768.0,
                                            batch_size_s=60,
                                            use_itn=True,
                                        )
                                        text = _extract_text(result)
                                    except Exception:
                                        text = ""
                                    if not text:
                                        deadline = time.monotonic() + 1.2
                                        while time.monotonic() < deadline and not text:
                                            try:
                                                item = results.get(timeout=0.05)
                                            except queue.Empty:
                                                continue
                                            if item.get("kind") == "final" and item.get("utterance_id") == utterance_id:
                                                text = item.get("text", "")
                                            elif item.get("kind") == "partial" and item.get("text") and on_partial:
                                                on_partial({"type": "partial_text", **item})
                                    if text:
                                        on_final({"type": "final_text", "text": text, "utterance_id": utterance_id, "source": "funasr_offline" if result else "funasr_online_fallback", "samples": samples})
                                on_partial and on_partial({"type": "speech_end", "utterance_id": utterance_id})
                                utterance_id += 1
                                utterance = []
                                speaking = False
                                silence_blocks = 0
                                pre_buffer.clear()
        finally:
            online.stop()

    @staticmethod
    def _drain_results(results, on_partial, on_final):
        while True:
            try:
                item = results.get_nowait()
            except queue.Empty:
                return
            if item.get("kind") == "partial" and item.get("text") and on_partial:
                on_partial({"type": "partial_text", **item})
            elif item.get("kind") == "final" and item.get("text") and on_partial:
                on_partial({"type": "online_final_text", **item})


class WhisperBackend(AsrBackend):
    """Local dual-condition VAD segmentation followed by Whisper HTTP."""

    def __init__(self, base_url, api_key, model="whisper-1", sample_rate=SAMPLE_RATE, silence_ms=SILENCE_GAP_MS):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.sample_rate = sample_rate
        self.block_samples = sample_rate // 10
        self.silence_ms = silence_ms

    def run(self, on_final, on_partial=None, stop_event=None):
        try:
            import numpy as np
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("Whisper voice dependencies are missing; install requirements-voice.txt") from exc
        if not self.base_url or not self.api_key:
            raise RuntimeError("Whisper backend requires MINIMOVER_WHISPER_URL and MINIMOVER_API_KEY")
        audio_queue = queue.Queue(maxsize=64)
        pre_buffer = deque(maxlen=int(PRE_ROLL_MS * self.sample_rate / 1000))
        speech = []
        silence_blocks = 0
        speaking = False
        utterance_id = 0
        noise_floor = 0.004

        def callback(indata, frames, time_info, status):
            del frames, time_info, status
            try:
                audio_queue.put_nowait(indata[:, 0].copy())
            except queue.Full:
                pass

        with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype="int16", blocksize=self.block_samples, callback=callback):
            while stop_event is None or not stop_event.is_set():
                try:
                    block = np.asarray(audio_queue.get(timeout=0.2), dtype=np.int16).reshape(-1)
                except queue.Empty:
                    continue
                pre_buffer.extend(block.tolist())
                level = _rms(block)
                if not speaking and level < max(0.015, noise_floor * 3.0):
                    noise_floor = 0.95 * noise_floor + 0.05 * max(level, 0.0005)
                active = level > max(0.003, noise_floor * 2.2)
                if active and not speaking:
                    speaking = True
                    speech = list(pre_buffer)
                    silence_blocks = 0
                    on_partial and on_partial({"type": "speech_start", "utterance_id": utterance_id})
                elif speaking:
                    speech.extend(block.tolist())
                    silence_blocks = 0 if active else silence_blocks + 1
                    if silence_blocks * BLOCK_MS >= self.silence_ms:
                        if len(speech) >= int(self.sample_rate * MIN_SPEECH_MS / 1000):
                            text = self._transcribe(np.asarray(speech, dtype=np.float32))
                            if text:
                                on_final({"type": "final_text", "text": text, "utterance_id": utterance_id, "source": "whisper", "samples": np.asarray(speech, dtype=np.int16)})
                        on_partial and on_partial({"type": "speech_end", "utterance_id": utterance_id})
                        utterance_id += 1
                        speech = []
                        speaking = False
                        silence_blocks = 0
                        pre_buffer.clear()

    def _transcribe(self, samples):
        import numpy as np
        pcm = (samples.clip(-1, 1) * 32767).astype(np.int16).tobytes()
        audio = io.BytesIO()
        with wave.open(audio, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm)
        boundary = "----MiniMoverVoice"
        body = (b"--" + boundary.encode() + b"\r\n" + b'Content-Disposition: form-data; name="file"; filename="speech.wav"\r\n' + b"Content-Type: audio/wav\r\n\r\n" + audio.getvalue() + b"\r\n--" + boundary.encode() + b"\r\n" + b'Content-Disposition: form-data; name="model"\r\n\r\n' + self.model.encode() + b"\r\n--" + boundary.encode() + b"--\r\n")
        req = request.Request(self.base_url + "/audio/transcriptions", data=body, headers={"Authorization": "Bearer " + self.api_key, "Content-Type": "multipart/form-data; boundary=" + boundary}, method="POST")
        with request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        return str(result.get("text", "")).strip()


def _rms(samples):
    import numpy as np
    return float(np.sqrt(np.mean((samples.astype(np.float32) / 32768.0) ** 2)))


def _extract_text(result):
    if isinstance(result, list) and result:
        result = result[0]
    if isinstance(result, dict):
        return str(result.get("text", "")).strip()
    return ""
