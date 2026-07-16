"""Car client: mic capture → WebSocket → PC ASR → TTS on wake."""
import json, os, sys, threading, time

import numpy as np
import sounddevice as sd
import websocket

from voice_assistant.audio_turn_safety import CaptureGate
from voice_assistant.demo_session_client import DemoWelcomePoller

SAMPLE_RATE = 16000
BLOCK_MS = 100
BLOCK_SAMPLES = SAMPLE_RATE * BLOCK_MS // 1000

ASR_HOST = os.environ.get("MINIMOVER_ASR_HOST", "192.168.137.1")
ASR_PORT = int(os.environ.get("MINIMOVER_ASR_PORT", "8765"))
WAKE_WORD = os.environ.get("MINIMOVER_WAKE_WORD", "你好小南")
GREETING = os.environ.get("MINIMOVER_WAKE_GREETING", "你好，我在")
CAR_URL = os.environ.get("MINIMOVER_CAR_URL", "http://127.0.0.1:5000")
CAR_NAME = os.environ.get("MINIMOVER_CAR_NAME", "")  # "??" or "??"
HOSPITAL_GUIDE_MODE = os.environ.get("MINIMOVER_HOSPITAL_GUIDE_MODE", "0").lower() in ("1", "true", "yes", "on")  # "小南" or "小北"
HOSPITAL_GUIDE_DEMO_MODE = os.environ.get("MINIMOVER_HOSPITAL_GUIDE_DEMO_MODE") == "1"
GUIDE_AWAKE_TIMEOUT = float(os.environ.get("MINIMOVER_WAKE_TIMEOUT", "30"))
_guide_awake_until = 0.0
_guide_state_lock = threading.Lock()
_guide_turn_lock = threading.Lock()


def _guide_mark_awake():
    global _guide_awake_until
    with _guide_state_lock:
        _guide_awake_until = time.monotonic() + GUIDE_AWAKE_TIMEOUT


def _guide_is_awake():
    with _guide_state_lock:
        return time.monotonic() < _guide_awake_until


def _guide_mark_asleep():
    global _guide_awake_until
    with _guide_state_lock:
        _guide_awake_until = 0.0



def _speak(text, capture_gate=None, send_control=None):
    """Synthesize and play one response while atomically muting microphone upload."""
    if capture_gate is not None:
        became_muted = capture_gate.begin_playback()
        if became_muted and send_control is not None:
            send_control({"type": "capture_gate", "active": True})

    duration_ms = 0
    try:
        import requests
        response = requests.post(f"{CAR_URL}/api/audio/say", json={"text": text}, timeout=30)
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
            # Only the final, still-current playback may reopen capture. A newer
            # reply that starts during this tail retains the server-side gate.
            if release is not None:
                remaining_mute_s, generation = release
                time.sleep(remaining_mute_s)
                if send_control is not None and capture_gate.can_release_capture(generation):
                    send_control({"type": "capture_gate", "active": False})


def _execute_command(cmd, dur_override=None):
    """Send a movement command to the car's /api/move endpoint."""
    try:
        import requests, time
        if cmd == "dance":
            import random
            lines = [
                "来啦来啦，看我扭一扭！咚咚锵咚咚锵~",
                "音乐响起来，屁股扭起来，左三圈右三圈~",
                "今天心情好，给你跳个舞！虽然我只有轮子，但我有灵魂！",
                "旋转跳跃我闭着眼，尘嚣看不见你沉醉了没~",
                "我是小可爱，也是小霸王，扭起来谁都挡不住！",
                "蹦瞎卡拉卡！蹦瞎卡拉卡！",
            ]
            say = random.choice(lines)
            print(f"DANCE: {say}", file=sys.stderr, flush=True)
            # Speak while dancing (TTS runs in parallel)
            threading.Thread(target=_speak, args=(say,), daemon=True).start()
            # Dance for ~10 seconds: big swings
            for _ in range(8):
                requests.post(f"{CAR_URL}/api/move", json={"cmd": "left", "speed": 80, "duration": 0.6}, timeout=5)
                time.sleep(0.65)
                requests.post(f"{CAR_URL}/api/move", json={"cmd": "right", "speed": 80, "duration": 0.6}, timeout=5)
                time.sleep(0.65)
            return
        if dur_override is not None and dur_override > 0:
            dur = float(dur_override)
        elif cmd in ("left", "right"):
            dur = 1.0  # ~90° turn
        elif cmd in ("forward", "backward"):
            dur = 0.5
        else:
            dur = 0.5
        r = requests.post(f"{CAR_URL}/api/move", json={"cmd": cmd, "speed": 50, "duration": dur}, timeout=5)
        print(f"MOVE: {cmd} dur={dur}s -> {r.json()}", file=sys.stderr, flush=True)
    except Exception as exc:
        print(f"MOVE error: {exc}", file=sys.stderr, flush=True)


def _handle_hospital_guide(text, capture_gate=None, send_control=None):
    if not _guide_is_awake():
        print("HOSPITAL_GUIDE ignored final_text before wake", flush=True)
        return
    try:
        # Keep guide turns and TTS replies ordered when ASR produces overlapping finals.
        with _guide_turn_lock:
            if not _guide_is_awake():
                print("HOSPITAL_GUIDE ignored expired turn", flush=True)
                return
            from hospital_guide_client import HospitalGuideClient
            reply = HospitalGuideClient(CAR_URL).process_final_text(text)
            _guide_mark_awake()
            print(f"HOSPITAL_GUIDE: {reply}", flush=True)
            _speak(reply, capture_gate=capture_gate, send_control=send_control)
    except Exception as exc:
        print(f"HOSPITAL_GUIDE error: {exc}", file=sys.stderr, flush=True)


def _demo_welcome_poller_enabled():
    return HOSPITAL_GUIDE_MODE and HOSPITAL_GUIDE_DEMO_MODE

def _demo_welcome_loop(poller, capture_gate, send_control, is_connected, pause=time.sleep):
    """Play claimed demo welcomes without allowing their audio into ASR."""
    while is_connected():
        try:
            payload = poller.poll_once()
        except Exception as exc:
            print(f"HOSPITAL_GUIDE demo welcome poll error: {exc}", file=sys.stderr, flush=True)
            payload = None
        if payload:
            _guide_mark_asleep()
            try:
                _speak(payload["text"], capture_gate=capture_gate, send_control=send_control)
            finally:
                _guide_mark_awake()
        pause(0.5)

def _on_message(ws, raw, capture_gate=None, send_control=None):
    """Handle messages from PC ASR server."""
    msg = json.loads(raw)
    mtype = msg.get("type", "")
    if mtype == "final_text":
        text = msg.get("text", "")
        print(f"ASR: {text}", flush=True)
        if HOSPITAL_GUIDE_MODE:
            if not _guide_is_awake():
                print("HOSPITAL_GUIDE ignored final_text before wake", flush=True)
                return
            threading.Thread(target=_handle_hospital_guide, args=(text, capture_gate, send_control), daemon=True).start()
    elif mtype == "wake_detected":
        print(f"WAKE: {msg.get('text', '')}", flush=True)
        if HOSPITAL_GUIDE_MODE:
            # The first guide query follows immediately; a greeting here would
            # overlap its answer and be recorded by the microphone.
            _guide_mark_awake()
        else:
            threading.Thread(
                target=_speak,
                args=(GREETING, capture_gate, send_control),
                daemon=True,
            ).start()
    elif mtype == "command":
        if HOSPITAL_GUIDE_MODE:
            print("HOSPITAL_GUIDE ignored legacy command", flush=True)
            return
        cmd = msg.get("cmd", "")
        dur = msg.get("duration", 0.5)
        print(f"CMD: {cmd} dur={dur}s ({msg.get('text','')})", flush=True)
        threading.Thread(target=_execute_command, args=(cmd, dur), daemon=True).start()
    elif mtype == "command_exit":
        if HOSPITAL_GUIDE_MODE:
            _guide_mark_asleep()
            print("HOSPITAL_GUIDE ignored legacy command_exit", flush=True)
            return
        print(f"EXIT: {msg.get('text','')}", flush=True)
        threading.Thread(target=_speak, args=("????????", capture_gate, send_control), daemon=True).start()
    elif mtype == "chat_reply":
        if HOSPITAL_GUIDE_MODE:
            print("HOSPITAL_GUIDE ignored legacy chat_reply", flush=True)
            return
        reply = msg.get("text", "")
        print(f"LLM: {reply[:80]}", flush=True)
        threading.Thread(target=_speak, args=(reply, capture_gate, send_control), daemon=True).start()
    elif mtype == "thinking":
        print(f"... {msg.get('text','')[:40]}", file=sys.stderr, flush=True)
    elif mtype == "speaker_rejected":
        print(f"REJECTED (sim={msg.get('similarity','?')}<{msg.get('threshold','?')})", file=sys.stderr, flush=True)
    elif mtype == "speech_start":
        print(f"SPEECH_START", file=sys.stderr, flush=True)
    elif mtype == "speech_end":
        print(f"SPEECH_END dur={msg.get('duration_ms','?')}ms", file=sys.stderr, flush=True)


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

    # Receive ready
    resp = ws.recv()
    print(f"Server: {resp}", file=sys.stderr, flush=True)

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

    # Send only routing information; secrets never cross the local ASR socket.
    _send_control({"type": "wake_word", "value": WAKE_WORD, "car_name": CAR_NAME})

    # Switch to non-blocking for audio streaming
    ws.settimeout(0.01)

    print(f"Mic: hw:2,0 @ {SAMPLE_RATE}Hz", file=sys.stderr, flush=True)

    def _audio_cb(indata, frames, timestamp, status):
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

    recv_thread = threading.Thread(target=_receive_loop, daemon=True)
    recv_thread.start()

    if _demo_welcome_poller_enabled():
        demo_poller = DemoWelcomePoller(base_url=CAR_URL)
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
            device="hw:2,0",
            callback=_audio_cb,
        ):
            print("Mic open, listening...", flush=True)
            # 播放准备就绪提示音
            # The startup prompt must obey the same capture gate as guide replies;
            # otherwise the microphone can transcribe the prompt itself.
            _speak("????", capture_gate=capture_gate, send_control=_send_control)
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
