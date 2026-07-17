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
from voice_assistant.demo_session_client import DemoWelcomePoller

SAMPLE_RATE = 16000
BLOCK_MS = 100
BLOCK_SAMPLES = SAMPLE_RATE * BLOCK_MS // 1000

ASR_HOST = os.environ.get("MINIMOVER_ASR_HOST", "192.168.137.1")
ASR_PORT = int(os.environ.get("MINIMOVER_ASR_PORT", "8765"))
CAR_URL = os.environ.get("MINIMOVER_CAR_URL", "http://127.0.0.1:5000")
CAR_NAME = os.environ.get("MINIMOVER_CAR_NAME", "")
HOSPITAL_GUIDE_DEMO_MODE = os.environ.get("MINIMOVER_HOSPITAL_GUIDE_DEMO_MODE") == "1"
ASR_ONLY = os.environ.get("MINIMOVER_ASR_ONLY") == "1"
_guide_turn_lock = threading.Lock()
_demo_state_lock = threading.Lock()
_demo_listening = not HOSPITAL_GUIDE_DEMO_MODE
_announced_arrival_sessions = set()
ARRIVAL_ANNOUNCEMENT = "\u5df2\u5230\u8fbe\u5185\u79d1\uff0c\u8bf7\u6ce8\u610f\u811a\u4e0b\u3002"


def _resolve_mic_device(devices=None):
    """Resolve the USB microphone by stable name instead of ALSA card number."""
    devices = list(sd.query_devices() if devices is None else devices)
    capture_devices = [
        (index, str(device.get("name", "")))
        for index, device in enumerate(devices)
        if int(device.get("max_input_channels", 0) or 0) > 0
    ]
    if not capture_devices:
        raise RuntimeError("no audio capture device is available")

    requested = os.environ.get("MINIMOVER_MIC_DEVICE", "").strip()
    if requested:
        if requested.isdigit():
            requested_index = int(requested)
            if any(index == requested_index for index, _name in capture_devices):
                return requested_index
        requested_folded = requested.casefold()
        matches = [
            index for index, name in capture_devices
            if requested_folded in name.casefold()
        ]
        if matches:
            return matches[0]
        raise RuntimeError("configured microphone was not found: %s" % requested)

    for preferred in ("xfm-dp", "iflytek", "usb audio"):
        for index, name in capture_devices:
            if preferred in name.casefold():
                return index
    for index, name in capture_devices:
        if "nvidia" not in name.casefold():
            return index
    return capture_devices[0][0]


def _demo_start_listening():
    global _demo_listening
    with _demo_state_lock:
        _demo_listening = True


def _demo_stop_listening():
    global _demo_listening
    with _demo_state_lock:
        _demo_listening = False


def _demo_is_listening():
    with _demo_state_lock:
        return _demo_listening


def _demo_welcome_poller_enabled():
    return HOSPITAL_GUIDE_DEMO_MODE


def _demo_welcome_loop(poller, capture_gate, send_control, is_connected, pause=time.sleep):
    """Speak one claimed face welcome, then accept hospital-guide turns."""
    while is_connected():
        try:
            payload = poller.poll_once()
        except Exception as exc:
            print(f"HOSPITAL_GUIDE demo welcome poll error: {exc}", file=sys.stderr, flush=True)
            payload = None
        if payload:
            _demo_stop_listening()
            try:
                _speak(payload["text"], capture_gate=capture_gate, send_control=send_control)
            finally:
                _demo_start_listening()
        else:
            status = _read_demo_status(poller)
            allowed = _sync_demo_listening(poller, status=status)
            announcement = _claim_demo_arrival_announcement(status)
            if announcement:
                if allowed is not False:
                    _demo_stop_listening()
                _speak(announcement, capture_gate=capture_gate, send_control=send_control)
        pause(0.5)


def _read_demo_status(poller):
    reader = getattr(poller, "read_status", None)
    if not callable(reader):
        return None
    try:
        return reader()
    except Exception as exc:
        print(f"HOSPITAL_GUIDE demo status read error: {exc}", file=sys.stderr, flush=True)
        return None


def _sync_demo_listening(poller, status=None):
    """Align local ASR gating with the server session after reconnect/reset."""
    try:
        if status is None:
            allowed = poller.listening_allowed()
        else:
            allowed = poller.listening_allowed(status)
    except Exception as exc:
        print(f"HOSPITAL_GUIDE demo status sync error: {exc}", file=sys.stderr, flush=True)
        return None
    if allowed is True:
        _demo_start_listening()
    elif allowed is False:
        _demo_stop_listening()
    return allowed


def _claim_demo_arrival_announcement(status):
    if not isinstance(status, dict):
        return None
    session = status.get("session")
    navigation = status.get("navigation")
    if not isinstance(session, dict) or not isinstance(navigation, dict):
        return None
    session_id = session.get("session_id")
    if (
        not isinstance(session_id, str)
        or not session_id
        or session.get("phase") != "ARRIVED"
        or session.get("department_id") != "internal_medicine"
        or navigation.get("status") != "SUCCEEDED"
        or navigation.get("arrived") is not True
    ):
        return None
    with _demo_state_lock:
        if session_id in _announced_arrival_sessions:
            return None
        _announced_arrival_sessions.add(session_id)
    return ARRIVAL_ANNOUNCEMENT


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
        if ASR_ONLY:
            print("HOSPITAL_GUIDE disabled in ASR-only test mode", flush=True)
            return
        if HOSPITAL_GUIDE_DEMO_MODE and not _demo_is_listening():
            print("HOSPITAL_GUIDE ignored final_text before face welcome", flush=True)
            return
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
    mic_device = _resolve_mic_device()
    mic_name = sd.query_devices(mic_device)["name"]
    print(
        f"Mic: {mic_name} [device={mic_device}] @ {SAMPLE_RATE}Hz",
        file=sys.stderr,
        flush=True,
    )

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
    if _demo_welcome_poller_enabled():
        demo_poller = DemoWelcomePoller(base_url=CAR_URL)
        _sync_demo_listening(demo_poller)
        threading.Thread(
            target=_demo_welcome_loop,
            args=(demo_poller, capture_gate, _send_control),
            kwargs={"is_connected": lambda: bool(ws.connected)},
            daemon=True,
        ).start()
    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=BLOCK_SAMPLES,
            device=mic_device,
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
