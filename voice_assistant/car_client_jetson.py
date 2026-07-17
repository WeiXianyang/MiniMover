"""Dedicated Jetson client for the five-minute hospital-guide demo."""
import json
import os
import sys
import threading
import time

# The Jetson launcher invokes this file directly. Add the project root so the
# package import below works the same way as ``python -m``.
if __package__ in (None, ""):
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)

import sounddevice as sd
import websocket

from voice_assistant.audio_turn_safety import CaptureGate

SAMPLE_RATE = 16000
BLOCK_MS = 100
BLOCK_SAMPLES = SAMPLE_RATE * BLOCK_MS // 1000

ASR_HOST = os.environ.get("MINIMOVER_ASR_HOST", "192.168.137.1")
ASR_PORT = int(os.environ.get("MINIMOVER_ASR_PORT", "8765"))
CAR_URL = os.environ.get("MINIMOVER_CAR_URL", "http://127.0.0.1:5000")
CAR_NAME = os.environ.get("MINIMOVER_CAR_NAME", "")
_guide_turn_lock = threading.Lock()


def _speak(text, capture_gate=None, send_control=None):
    """Synthesize and play one guide response while muting microphone upload."""
    if capture_gate is not None:
        became_muted = capture_gate.begin_playback()
        if became_muted and send_control is not None:
            send_control({"type": "capture_gate", "active": True})

    duration_ms = 0
    try:
        import requests

        response = requests.post(
            f"{CAR_URL}/api/audio/say", json={"text": text}, timeout=30
        )
        response.raise_for_status()
        body = response.json()
        if body.get("code") != 0:
            raise RuntimeError(body.get("msg", "TTS request failed"))
        duration_ms = int(body.get("data", {}).get("playback_duration_ms", 0) or 0)
        print(f"TTS: {body}", file=sys.stderr, flush=True)
    except Exception as exc:
        print(f"TTS error: {exc}", file=sys.stderr, flush=True)
    finally:
        if capture_gate is not None:
            release = capture_gate.finish_playback(duration_ms)
            if release is not None:
                remaining_mute_s, generation = release
                time.sleep(remaining_mute_s)
                if send_control is not None and capture_gate.can_release_capture(generation):
                    send_control({"type": "capture_gate", "active": False})


def _handle_hospital_guide(text, capture_gate, send_control):
    """Send one finalized ASR turn to the hospital-guide API, then speak it."""
    normalized = str(text or "").strip()
    if not normalized:
        return
    try:
        # Keep guide responses and TTS playback ordered if ASR sends close turns.
        with _guide_turn_lock:
            from voice_assistant.hospital_guide_client import HospitalGuideClient

            reply = HospitalGuideClient(CAR_URL).process_final_text(normalized)
            print(f"HOSPITAL_GUIDE: {reply}", flush=True)
            _speak(reply, capture_gate=capture_gate, send_control=send_control)
    except Exception as exc:
        print(f"HOSPITAL_GUIDE error: {exc}", file=sys.stderr, flush=True)


def _on_message(_ws, raw, capture_gate=None, send_control=None):
    """Handle only finalized guide text and ASR status from the dedicated relay."""
    try:
        msg = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        print(f"ASR message error: {exc}", file=sys.stderr, flush=True)
        return

    mtype = msg.get("type", "")
    if mtype == "final_text":
        text = msg.get("text", "")
        print(f"ASR: {text}", flush=True)
        threading.Thread(
            target=_handle_hospital_guide,
            args=(text, capture_gate, send_control),
            daemon=True,
        ).start()
    elif mtype == "speech_start":
        print("SPEECH_START", file=sys.stderr, flush=True)
    elif mtype == "speech_end":
        print(f"SPEECH_END dur={msg.get('duration_ms', '?')}ms", file=sys.stderr, flush=True)


def main():
    while True:
        try:
            _connect_and_stream()
        except KeyboardInterrupt:
            break
        except Exception as exc:
            print(f"Disconnected: {exc}", file=sys.stderr, flush=True)
        print("Reconnecting in 1s...", file=sys.stderr, flush=True)
        time.sleep(1)


def _connect_and_stream():
    url = f"ws://{ASR_HOST}:{ASR_PORT}/ws/asr"
    print(f"Connecting to {url}...", file=sys.stderr, flush=True)

    ws = websocket.WebSocket()
    ws.settimeout(10)
    ws.connect(url)
    print(f"Server: {ws.recv()}", file=sys.stderr, flush=True)

    send_lock = threading.Lock()
    capture_gate = CaptureGate(
        post_playback_ms=int(os.environ.get("MINIMOVER_CAPTURE_POST_PLAYBACK_MS", "650"))
    )

    def _send_control(payload):
        try:
            with send_lock:
                ws.send(json.dumps(payload, ensure_ascii=False))
        except Exception as exc:
            print(f"Control send error: {exc}", file=sys.stderr, flush=True)

    _send_control({"type": "guide_mode", "car_name": CAR_NAME})
    ws.settimeout(0.01)
    print(f"Mic: hw:2,0 @ {SAMPLE_RATE}Hz", file=sys.stderr, flush=True)

    def _audio_cb(indata, _frames, _timestamp, status):
        if status:
            print(f"Mic: {status}", file=sys.stderr, flush=True)
        if capture_gate.is_muted():
            return
        try:
            with send_lock:
                ws.send_binary(indata.tobytes())
        except websocket.WebSocketTimeoutException:
            pass
        except Exception as exc:
            print(f"Send error: {exc}", file=sys.stderr, flush=True)

    receive_running = [True]

    def _receive_loop():
        while receive_running[0]:
            try:
                data = ws.recv()
                if data:
                    _on_message(ws, data, capture_gate=capture_gate, send_control=_send_control)
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as exc:
                print(f"Recv error: {exc}", file=sys.stderr, flush=True)
                break

    threading.Thread(target=_receive_loop, daemon=True).start()
    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=BLOCK_SAMPLES,
            device="hw:2,0",
            callback=_audio_cb,
        ):
            print("Mic open, listening...", flush=True)
            while ws.connected:
                time.sleep(0.5)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr, flush=True)
    finally:
        receive_running[0] = False
        try:
            ws.close()
        except Exception:
            pass
    print("Stopped", flush=True)


if __name__ == "__main__":
    main()
