"""PC ASR Relay — VAD + DashScope 百炼 ASR, WebSocket audio from car.

Endpoints:   ws://0.0.0.0:PORT/ws/asr      — car audio stream
             ws://0.0.0.0:PORT/ws/monitor  — dashboard view-only
"""
import asyncio, json, math, os, sys

# Support both ``python -m voice_assistant.pc_asr_server`` and the direct
# script invocation used by the existing Windows/Jetson launchers.
if __package__ in (None, ""):
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
from collections import deque

import numpy as np
import websockets
from websockets.asyncio.server import serve

from voice_assistant.asr_backends import recognize_utterance
from voice_assistant.audio_turn_safety import normalized_rms

# ═══ 自己加载 .env.* — 永远不依赖外部环境 ═══
_ENV_LOADED = False
for _env_file in (".env.voice", ".tts.env"):
    _path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", _env_file)
    if os.path.isfile(_path):
        with open(_path, "r", encoding="utf-8-sig") as _fh:
            for _line in _fh:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k, _v = _k.strip(), _v.strip()
                    if _v and not os.environ.get(_k):
                        os.environ[_k] = _v
                        _ENV_LOADED = True
if _ENV_LOADED:
    print("[env] loaded from .env.voice / .tts.env", file=sys.stderr, flush=True)

# DashScope SDK reads DASHSCOPE_API_KEY — 无条件用 .env.voice 的值覆盖，防止系统环境变量残留
api_key = os.environ.get("MINIMOVER_DASHSCOPE_API_KEY", "")
if api_key:
    os.environ["DASHSCOPE_API_KEY"] = api_key

# DashScope ASR backend configuration.
_DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
_DASHSCOPE_WS = os.environ.get("MINIMOVER_DASHSCOPE_WORKSPACE_ID", "").strip()
_ASR_PROVIDER = os.environ.get("MINIMOVER_ASR_PROVIDER", "paraformer").strip().lower()
_ASR_FALLBACK_PROVIDER = os.environ.get(
    "MINIMOVER_ASR_FALLBACK_PROVIDER", ""
).strip().lower()
_QWEN3_ASR_MODEL = os.environ.get(
    "MINIMOVER_QWEN3_ASR_MODEL", "qwen3-asr-flash"
).strip()
# Keep MINIMOVER_ASR_MODEL as a compatibility alias for existing deployments.
_PARAFORMER_ASR_MODEL = os.environ.get(
    "MINIMOVER_PARAFORMER_ASR_MODEL",
    os.environ.get("MINIMOVER_ASR_MODEL", "paraformer-realtime-v2"),
).strip()
_ASR_LANGUAGE = os.environ.get("MINIMOVER_ASR_LANGUAGE", "zh").strip()
_QWEN3_ASR_SYSTEM_PROMPT = os.environ.get(
    "MINIMOVER_QWEN3_ASR_SYSTEM_PROMPT", ""
).strip()
_DASHSCOPE_BASE_HTTP_API_URL = os.environ.get(
    "MINIMOVER_DASHSCOPE_BASE_HTTP_API_URL", ""
).strip()
_ASR_SAMPLE_RATE = 16000

if not _DASHSCOPE_API_KEY:
    print("[ASR] FATAL: MINIMOVER_DASHSCOPE_API_KEY not set!", file=sys.stderr, flush=True)
    sys.exit(1)
print(
    f"[env] DashScope workspace configured={bool(_DASHSCOPE_WS)} "
    f"provider={_ASR_PROVIDER} fallback={_ASR_FALLBACK_PROVIDER or 'disabled'}",
    file=sys.stderr,
    flush=True,
)


def _dashscope_asr(pcm_samples: np.ndarray) -> str:
    """Recognize one VAD-delimited utterance through the configured backend."""
    text = recognize_utterance(
        pcm_samples,
        provider=_ASR_PROVIDER,
        fallback_provider=_ASR_FALLBACK_PROVIDER,
        api_key=_DASHSCOPE_API_KEY,
        workspace=_DASHSCOPE_WS,
        qwen3_model=_QWEN3_ASR_MODEL,
        paraformer_model=_PARAFORMER_ASR_MODEL,
        language=_ASR_LANGUAGE,
        system_prompt=_QWEN3_ASR_SYSTEM_PROMPT,
        sample_rate=_ASR_SAMPLE_RATE,
        base_http_api_url=_DASHSCOPE_BASE_HTTP_API_URL,
    )
    print(
        f"[ASR] completed provider={_ASR_PROVIDER} "
        f"dur={len(pcm_samples) / _ASR_SAMPLE_RATE:.2f}s text_len={len(text)}",
        file=sys.stderr,
        flush=True,
    )
    return text


SAMPLE_RATE = 16000
BLOCK_MS = 200
BLOCK_SAMPLES = SAMPLE_RATE * BLOCK_MS // 1000  # 3200
PRE_ROLL_MS = 400
MIN_SPEECH_MS = 300
SILENCE_GAP_MS = int(os.environ.get("MINIMOVER_ASR_END_SILENCE_MS", "1200"))

def _rms(block):
    """RMS normalized to the signed 16-bit PCM range."""
    return normalized_rms(block.tolist())

# ── VAD model (Silero) ───────────────────────────────────────────
_silero_vad = None
_get_speech_ts = None

def _load_vad():
    global _silero_vad, _get_speech_ts
    if _silero_vad is not None:
        return _silero_vad
    print("[ASR] Loading Silero VAD...", file=sys.stderr, flush=True)
    from silero_vad import load_silero_vad as _lsv, get_speech_timestamps as _gst
    _silero_vad = _lsv(onnx=True)
    _get_speech_ts = _gst
    print(f"[ASR] Ready (provider={_ASR_PROVIDER})", file=sys.stderr, flush=True)
    return _silero_vad

_monitors = set()

async def _broadcast(data):
    dead = set()
    for mws in _monitors:
        try: await mws.send(data)
        except Exception: dead.add(mws)
    _monitors.difference_update(dead)

async def handle_monitor(ws):
    _monitors.add(ws)
    await ws.send(json.dumps({"type": "monitor_ready"}))
    try:
        async for _ in ws: pass
    finally:
        _monitors.discard(ws)


# ════════════════════════════════════════════════════════════════════
#  CAR  AUDIO  HANDLER
# ════════════════════════════════════════════════════════════════════
async def handle_car(ws):
    car_id = str(id(ws))[-6:]
    print(f"[{car_id}] Car connected", file=sys.stderr, flush=True)

    _load_vad()  # Silero VAD only, no heavy FunASR

    pre_buffer = deque(maxlen=int(PRE_ROLL_MS * SAMPLE_RATE / 1000))
    utterance, speaking, silence_blocks = [], False, 0
    uid, chunk_idx = 0, 0
    noise_floor = 0.004
    capture_muted = False
    log_prefix = f"[{car_id}]"

    await ws.send(json.dumps({"type": "ready"}))

    async def _send_status(state, **extra):
        payload = json.dumps({"type": state, **extra})
        try: await ws.send(payload)
        except Exception: pass
        await _broadcast(payload)

    try:
        async for message in ws:
            if isinstance(message, str):
                msg = json.loads(message)
                if msg.get("type") == "guide_mode":
                    car_name = msg.get("car_name", "")
                    log_prefix = f"[{car_name}:{car_id}]" if car_name else f"[{car_id}]"
                    print(
                        f"{log_prefix} Hospital guide client configured",
                        file=sys.stderr,
                        flush=True,
                    )
                elif msg.get("type") == "capture_gate":
                    capture_muted = bool(msg.get("active"))
                    # Discard partial speech at both TTS boundaries; otherwise a
                    # speaker tail can be joined to the next user utterance.
                    utterance = []
                    speaking = False
                    silence_blocks = 0
                    pre_buffer.clear()
                    await _send_status("capture_gate", active=capture_muted)
                continue

            if capture_muted:
                continue

            block = np.frombuffer(message, dtype=np.int16).copy()
            if len(block) == 0: continue

            pre_buffer.extend(block.tolist())
            level = _rms(block)

            if not speaking:
                # Adapt to constant cabin noise before applying speech thresholds.
                # `level` and `noise_floor` are both normalized PCM amplitudes.
                noise_floor = 0.98 * noise_floor + 0.02 * max(level, 0.0005)
            snr_db = 20 * math.log10((level + 1e-8) / (noise_floor + 1e-8))

            energy_hit = snr_db > 6.0 and level > max(0.012, noise_floor * 2.2)
            if energy_hit or speaking:
                vad_window = np.asarray(pre_buffer, dtype=np.float32) / 32768.0
                speech_ts = _get_speech_ts(vad_window, _silero_vad, threshold=0.35,
                    return_seconds=False, min_speech_duration_ms=MIN_SPEECH_MS,
                    min_silence_duration_ms=SILENCE_GAP_MS)
                vad_hit = bool(speech_ts)
            else:
                vad_hit = False

            voice_start = bool(vad_hit and snr_db > 6.0 and level > max(0.012, noise_floor * 2.2))
            voice_continue = bool(vad_hit and snr_db > 3.0 and level > max(0.006, noise_floor * 1.5))

            # vad_status broadcast
            await _broadcast(json.dumps({
                "type": "vad_status", "car_id": car_id,
                "level": round(level, 5), "snr_db": round(snr_db, 1),
                "noise_floor": round(noise_floor, 5),
                "vad_hit": bool(vad_hit), "energy_hit": bool(energy_hit),
                "speaking": bool(speaking), "state": "speech" if speaking else ("vad_hit" if vad_hit else "silence"),
                "uid": uid, "silence_blocks": silence_blocks,
            }))

            if not speaking and voice_start:
                speaking = True
                utterance = list(pre_buffer)
                silence_blocks = chunk_idx = 0
                await _send_status("speech_start", uid=uid)
                print(f"[{car_id} SPEECH_START uid={uid}", file=sys.stderr, flush=True)

            elif speaking:
                utterance.extend(block.tolist())
                if voice_continue:
                    silence_blocks = 0
                else:
                    silence_blocks += 1
                    if silence_blocks * BLOCK_MS >= SILENCE_GAP_MS:
                        samples = np.asarray(utterance, dtype=np.int16)
                        dur_ms = len(samples) * 1000.0 / SAMPLE_RATE
                        if dur_ms >= MIN_SPEECH_MS:
                            # DashScope ASR call.
                            loop = asyncio.get_running_loop()
                            text = await loop.run_in_executor(None, _dashscope_asr, samples)

                            if text:
                                normalized_text = text.strip()
                                if len(normalized_text) <= 1 or (
                                    len(normalized_text) < 3
                                    and any(char in normalized_text for char in "\u55ef\u554a\u54e6\u5443\u5514")
                                ):
                                    print(
                                        f"{log_prefix} GUIDE skip filler: {text}",
                                        file=sys.stderr,
                                        flush=True,
                                    )
                                else:
                                    sim, verified = 1.0, True
                                    await _broadcast(json.dumps({
                                        "type": "speaker_sim", "similarity": round(sim, 4),
                                        "verified": verified, "uid": uid, "car_id": car_id,
                                    }))
                                    await _send_status(
                                        "final_text", text=text, uid=uid,
                                        speaker_sim=round(sim, 4), speaker_ok=verified,
                                    )
                                    print(
                                        f"{log_prefix} GUIDE final: {text}",
                                        file=sys.stderr,
                                        flush=True,
                                    )

                            await _send_status("speech_end", uid=uid, duration_ms=round(dur_ms, 0))
                            print(f"[{car_id} SPEECH_END uid={uid} dur={dur_ms:.0f}ms", file=sys.stderr, flush=True)

                        uid += 1
                        utterance = []
                        speaking = False
                        silence_blocks = 0
                        pre_buffer.clear()

    except Exception as exc:
        print(f"[{car_id} Error: {exc}", file=sys.stderr, flush=True)
        import traceback; traceback.print_exc(file=sys.stderr)
    finally:
        print(f"[{car_id} Car disconnected", file=sys.stderr, flush=True)


# ════════════════════════════════════════════════════════════════════
async def dispatch(ws):
    path = ws.request.path if hasattr(ws, 'request') else "/ws/asr"
    if path.endswith("/monitor"):
        await handle_monitor(ws)
    else:
        await handle_car(ws)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"PC ASR (DashScope/{_ASR_PROVIDER}) : ws://0.0.0.0:{port}/ws/asr", file=sys.stderr, flush=True)
    print(f"Monitor            : ws://0.0.0.0:{port}/ws/monitor", file=sys.stderr, flush=True)
    _load_vad()

    async def _serve():
        async with serve(dispatch, "0.0.0.0", port):
            await asyncio.Future()

    asyncio.run(_serve())
