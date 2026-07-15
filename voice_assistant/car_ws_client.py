"""Car client: mic capture → WebSocket → PC ASR → TTS on wake."""
import json, os, sys, threading, time

import numpy as np
import sounddevice as sd
import websocket

SAMPLE_RATE = 16000
BLOCK_MS = 100
BLOCK_SAMPLES = SAMPLE_RATE * BLOCK_MS // 1000

ASR_HOST = os.environ.get("MINIMOVER_ASR_HOST", "192.168.137.1")
ASR_PORT = int(os.environ.get("MINIMOVER_ASR_PORT", "8765"))
WAKE_WORD = os.environ.get("MINIMOVER_WAKE_WORD", "你好小南")
GREETING = os.environ.get("MINIMOVER_WAKE_GREETING", "你好，我在")
CAR_URL = os.environ.get("MINIMOVER_CAR_URL", "http://127.0.0.1:5000")
CAR_NAME = os.environ.get("MINIMOVER_CAR_NAME", "")  # "小南" or "小北"


def _speak(text):
    """Call car's TTS endpoint (DashScope via api_server)."""
    try:
        import requests
        r = requests.post(f"{CAR_URL}/api/audio/say", json={"text": text}, timeout=5)
        print(f"TTS: {r.json()}", file=sys.stderr, flush=True)
    except Exception as exc:
        print(f"TTS error: {exc}", file=sys.stderr, flush=True)


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
            dur = 3.0
        elif cmd in ("forward", "backward"):
            dur = 3.0
        else:
            dur = 3.0
        r = requests.post(f"{CAR_URL}/api/move", json={"cmd": cmd, "speed": 50, "duration": dur}, timeout=5)
        print(f"MOVE: {cmd} dur={dur}s -> {r.json()}", file=sys.stderr, flush=True)
        time.sleep(dur)
        requests.post(f"{CAR_URL}/api/move", json={"cmd": "stop", "speed": 0, "duration": 0}, timeout=5)
        print(f"MOVE: stop", file=sys.stderr, flush=True)
    except Exception as exc:
        print(f"MOVE error: {exc}", file=sys.stderr, flush=True)


def _on_message(ws, raw):
    """Handle messages from PC ASR server."""
    msg = json.loads(raw)
    mtype = msg.get("type", "")
    if mtype == "final_text":
        print(f"ASR: {msg['text']}", flush=True)
    elif mtype == "wake_detected":
        print(f"WAKE: {msg.get('text', '')}", flush=True)
        threading.Thread(target=_speak, args=(GREETING,), daemon=True).start()
    elif mtype == "command":
        cmd = msg.get("cmd", "")
        dur = msg.get("duration", 0.5)
        print(f"CMD: {cmd} dur={dur}s ({msg.get('text','')})", flush=True)
        threading.Thread(target=_execute_command, args=(cmd, dur), daemon=True).start()
    elif mtype == "command_exit":
        print(f"EXIT: {msg.get('text','')}", flush=True)
        threading.Thread(target=_speak, args=("好的，有事再叫我",), daemon=True).start()
    elif mtype == "chat_reply":
        reply = msg.get("text", "")
        print(f"LLM: {reply[:80]}", flush=True)
        threading.Thread(target=_speak, args=(reply,), daemon=True).start()
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

    # Send wake word config (including API key for LLM)
    api_key = os.environ.get("MINIMOVER_DASHSCOPE_API_KEY", "")
    ws.send(json.dumps({"type": "wake_word", "value": WAKE_WORD, "api_key": api_key, "car_name": CAR_NAME}))

    # Switch to non-blocking for audio streaming
    ws.settimeout(0.01)

    print(f"Mic: hw:2,0 @ {SAMPLE_RATE}Hz", file=sys.stderr, flush=True)

    mute_until = [0.0]  # list for mutability in closure

    def _audio_cb(indata, frames, timestamp, status):
        if status:
            print(f"Mic: {status}", file=sys.stderr, flush=True)
        if time.monotonic() < mute_until[0]:
            return  # muted after TTS to avoid echo
        try:
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
                    _on_message(ws, data)
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as exc:
                print(f"Recv error: {exc}", file=sys.stderr, flush=True)
                break

    recv_thread = threading.Thread(target=_receive_loop, daemon=True)
    recv_thread.start()

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
