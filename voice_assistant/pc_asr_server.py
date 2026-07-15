"""PC ASR Server — MyMeeting VAD+ASR pipeline, WebSocket audio from car.

Endpoints:   ws://0.0.0.0:PORT/ws/asr      — car audio stream
             ws://0.0.0.0:PORT/ws/monitor  — dashboard view-only
"""
import asyncio, json, math, os, re, sys, time, queue, threading
from collections import deque

import numpy as np
import websockets
from websockets.asyncio.server import serve
from pypinyin import lazy_pinyin


def _to_pinyin(text):
    return ''.join(lazy_pinyin(text)).lower()

# Homophone groups: ASR often confuses these
_HOMOPHONE_MAP = {
    'n': 'n', 'l': 'n',  # n/l confusion (南/兰)
    'zh': 'z', 'z': 'z',  # zh/z (中/宗)
    'ch': 'c', 'c': 'c',  # ch/c
    'sh': 's', 's': 's',  # sh/s
    'h': 'h', 'f': 'h',  # h/f confusion
    'r': 'r', 'y': 'r',  # r/y confusion (rare)
}

def _fuzzy_pinyin(text):
    """Pinyin with common confusions collapsed."""
    p = _to_pinyin(text)
    # Collapse confusable initials
    for pair in [('zh','z'), ('ch','c'), ('sh','s'), ('l','n'), ('f','h')]:
        p = p.replace(pair[0], pair[1])
    # Collapse confusable finals (ai/ei, an/en, etc.)
    for pair in [('ei','ai'), ('en','an'), ('ing','in'), ('eng','en')]:
        p = p.replace(pair[0], pair[1])
    return p

# ── Constants from MyMeeting asr_backend.py ──────────────────────────
SAMPLE_RATE = 16000
BLOCK_MS = 200
BLOCK_SAMPLES = SAMPLE_RATE * BLOCK_MS // 1000
PRE_ROLL_MS = 400
MIN_SPEECH_MS = 300
SILENCE_GAP_MS = 800
STREAMING_CHUNK_SIZE = [0, 10, 5]
STREAMING_CHUNK_SAMPLES = STREAMING_CHUNK_SIZE[1] * 960


def _rms(block):
    return np.sqrt(np.mean(block.astype(np.float64) ** 2))


def _extract_text(result):
    if isinstance(result, list):
        return " ".join(r.get("text", "") if isinstance(r, dict) else str(r) for r in result)
    if isinstance(result, dict):
        return result.get("text", "")
    if isinstance(result, str):
        return result
    return ""


class OnlineWorker:
    """Background thread that calls FunASR generate() without blocking the event loop."""
    def __init__(self, model, on_result, max_queue=16):
        self.model = model
        self.on_result = on_result
        self.tasks = queue.Queue(maxsize=max_queue)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.stop_event = threading.Event()
        self.cache = {}
        self.thread.start()

    def submit(self, uid, samples, is_final, chunk_idx):
        try:
            self.tasks.put_nowait((uid, samples, is_final, chunk_idx))
            return True
        except queue.Full:
            try:
                self.tasks.get_nowait()
            except queue.Empty:
                pass
            try:
                self.tasks.put_nowait((uid, samples, is_final, chunk_idx))
                return True
            except queue.Full:
                return False

    def _run(self):
        while not self.stop_event.is_set():
            try:
                uid, samples, is_final, chunk_idx = self.tasks.get(timeout=0.1)
            except queue.Empty:
                continue
            started = time.perf_counter()
            try:
                result = self.model.generate(
                    input=samples.astype("float32") / 32768.0,
                    cache=self.cache, is_final=is_final,
                    chunk_size=STREAMING_CHUNK_SIZE,
                    encoder_chunk_look_back=4, decoder_chunk_look_back=1,
                )
                text = _extract_text(result)
                self.on_result({"kind": "final" if is_final else "partial",
                    "utterance_id": uid, "chunk_index": chunk_idx,
                    "text": text, "asr_ms": round((time.perf_counter()-started)*1000,1)})
                if is_final:
                    self.cache = {}
            except Exception as exc:
                self.on_result({"kind": "error", "utterance_id": uid, "error": str(exc)})

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=1.0)


# ── Model cache ─────────────────────────────────────────────────────
_models = None
_speaker_model = None
_speaker_profiles = []  # list of (name, embedding)

SPEAKER_THRESHOLD = 0.15
SPEAKER_PROFILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "speaker_profile.npy")

# ── Command vocabulary ───────────────────────────────────────────────
_COMMAND_PATTERNS = (
    ("forward", ("前进", "进前", "向前", "前往", "往前走", "向前走", "往前", "走")),
    ("backward", ("后退", "退后", "向后", "后向", "往后走", "向后走", "倒退")),
    ("stop",   ("急停", "停止", "停下来", "停下", "别动", "不要动")),
    ("left",   ("向左转", "向左", "左转", "转左", "往左转", "往左")),
    ("right",  ("向右转", "向右", "右转", "转右", "往右转", "往右")),
    ("spin",   ("转圈", "圈转", "原地转", "旋转一圈", "转个圈")),
    ("dance",  ("跳舞", "舞跳", "跳个舞", "跳个舞吧", "扭起来", "扭一扭", "摇起来", "摇摆", "来段舞", "跳支舞")),
)
_EXIT_PATTERNS = ("再见", "见再", "拜拜", "休息", "睡觉", "退下", "没事了", "不说了", "先这样")
_EXIT_REPLY = "好的，有事再叫我"

AWAKE_TIMEOUT = 300.0  # seconds before falling back to IDLE
_LLM_API_KEY = os.environ.get("MINIMOVER_DASHSCOPE_API_KEY", os.environ.get("DASHSCOPE_API_KEY", ""))
_LLM_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
_LLM_MODEL = "qwen-turbo"
_LLM_SYSTEM = "你是一个小车车载助手，名叫小南。用简短、口语化的中文回复, 20字以内最佳。"


def _ask_llm(text):
    """Send text to DashScope Qwen, return reply string or None."""
    if not _LLM_API_KEY:
        return None
    try:
        from urllib import request as _req
        payload = json.dumps({
            "model": _LLM_MODEL,
            "messages": [
                {"role": "system", "content": _LLM_SYSTEM},
                {"role": "user", "content": text},
            ],
            "max_tokens": 80,
            "temperature": 0.7,
        }, ensure_ascii=False).encode("utf-8")
        headers = {"Authorization": "Bearer " + _LLM_API_KEY, "Content-Type": "application/json"}
        req = _req.Request(_LLM_URL, data=payload, headers=headers, method="POST")
        with _req.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        reply = body["choices"][0]["message"]["content"].strip()
        print(f"[LLM] Q: {text[:40]} -> A: {reply[:60]}", file=sys.stderr, flush=True)
        return reply
    except Exception as exc:
        print(f"[LLM] Error: {exc}", file=sys.stderr, flush=True)
        return None


def _normalize_text(text):
    return re.sub(r"[，。！？、,.!?；;：:‘'"" ]", "", (text or "").strip())


def _parse_command(text):
    if not text:
        return None
    clean = _normalize_text(text)
    for cmd, phrases in _COMMAND_PATTERNS:
        if any(phrase in clean for phrase in phrases):
            result = {"cmd": cmd}
            m = re.search(r"(\d+|[一二三四五六七八九十])\s*秒", text)
            if m:
                num_str = m.group(1)
                num_map = {"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
                dur = num_map.get(num_str, None)
                if dur is None:
                    try: dur = int(num_str)
                    except ValueError: dur = None
                if dur and 0 < dur <= 30:
                    result["duration"] = float(dur)
            return result
    return None


def _is_exit(text):
    """Check if text is an exit/disengage command."""
    clean = _normalize_text(text)
    return any(phrase in clean for phrase in _EXIT_PATTERNS)


def _cosine_sim(left, right):
    left, right = np.asarray(left, np.float32).ravel(), np.asarray(right, np.float32).ravel()
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.dot(left, right) / denom) if denom > 1e-8 else 0.0


def _load_models():
    global _models, _speaker_model, _speaker_profiles
    if _models is not None:
        return _models
    print("[ASR] Importing...", file=sys.stderr, flush=True)
    import torch as _t
    from funasr import AutoModel as _AM
    from silero_vad import load_silero_vad as _lsv, get_speech_timestamps as _gst
    device = "cuda:0" if _t.cuda.is_available() else "cpu"
    name = _t.cuda.get_device_name(0) if _t.cuda.is_available() else "CPU"
    print(f"[ASR] Loading paraformer on {device} ({name})...", file=sys.stderr, flush=True)
    m = _AM(model="paraformer-zh-streaming", device=device, disable_update=True, disable_pbar=True)
    s = _lsv(onnx=True)
    # Load CAM++ speaker verification model
    print("[ASR] Loading CAM++ speaker model...", file=sys.stderr, flush=True)
    _speaker_model = _AM(model="iic/speech_campplus_sv_zh-cn_16k-common", device=device, disable_update=True, disable_pbar=True)
    # Load speaker profiles
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for fname, label in [("speaker_profile.npy", "user"), ("speaker_profile_nan.npy", "小南"), ("speaker_profile_bei.npy", "小北")]:
        pp = os.path.join(base_dir, fname)
        if os.path.isfile(pp):
            emb = np.load(pp).astype(np.float32).ravel()
            _speaker_profiles.append((label, emb))
            print(f"[ASR] Speaker profile '{label}' loaded (dim={len(emb)})", file=sys.stderr, flush=True)
    if not _speaker_profiles:
        print(f"[ASR] WARNING: no speaker profiles found", file=sys.stderr, flush=True)
    _models = (m, s, _gst)
    print("[ASR] Ready", file=sys.stderr, flush=True)
    return _models


def _identify_speaker(audio_int16, profiles=None):
    """CAM++ speaker verification against allowed profiles.
    Returns (best_similarity: float, verified: bool).  If no profile, returns (1.0, True)."""
    if profiles is None:
        profiles = _speaker_profiles
    if _speaker_model is None or not profiles:
        return 1.0, True
    try:
        audio_float = audio_int16.astype(np.float32) / 32768.0
        res = _speaker_model.generate(input=audio_float)
        if res and len(res) > 0 and isinstance(res[0], dict) and 'spk_embedding' in res[0]:
            raw = res[0]['spk_embedding']
            if hasattr(raw, 'cpu'):
                raw = raw.cpu().numpy()
            emb = np.asarray(raw, dtype=np.float32).reshape(-1)
            # Check against allowed profiles, take best match
            best_sim, best_name = -1.0, "?"
            for name, prof in profiles:
                sim = _cosine_sim(emb, prof)
                if sim > best_sim:
                    best_sim, best_name = sim, name
            verified = best_sim >= SPEAKER_THRESHOLD
            if verified:
                print(f"[Speaker] matched {best_name} (sim={best_sim:.3f})", file=sys.stderr, flush=True)
            return best_sim, verified
    except Exception as exc:
        print(f"[Speaker] Error: {exc}", file=sys.stderr, flush=True)
    return 1.0, True  # fail open


# ── Monitor registry ────────────────────────────────────────────────
_monitors = set()


async def _broadcast(data):
    """Send JSON to every connected monitor; drop dead ones silently."""
    dead = set()
    for mws in _monitors:
        try:
            await mws.send(data)
        except Exception:
            dead.add(mws)
    _monitors.difference_update(dead)


async def handle_monitor(ws):
    """View-only endpoint: receives no data, just gets status events."""
    _monitors.add(ws)
    await ws.send(json.dumps({"type": "monitor_ready"}))
    try:
        async for _ in ws:
            pass  # ignore any message
    finally:
        _monitors.discard(ws)


# ═══════════════════════════════════════════════════════════════════════
#  CAR  AUDIO  HANDLER
# ═══════════════════════════════════════════════════════════════════════
async def handle_car(ws):
    car_id = str(id(ws))[-6:]
    print(f"[{car_id}] Car connected", file=sys.stderr, flush=True)

    model, silero, get_speech_ts = _load_models()
    results = queue.Queue()
    worker = OnlineWorker(model, results.put)

    pre_buffer = deque(maxlen=int(PRE_ROLL_MS * SAMPLE_RATE / 1000))
    utterance, speaking, silence_blocks = [], False, 0
    uid, chunk_idx = 0, 0
    noise_floor, last_partial = 0.004, 0
    wake_word, awake_until = "", 0.0
    tts_mute_until = 0.0  # anti-echo mute after TTS
    allowed_profiles = None  # set when car identity received
    log_prefix = f"[{car_id}]"  # may be updated after car identity
    block_n = 0  # debug

    await ws.send(json.dumps({"type": "ready"}))

    async def _send_status(state, **extra):
        """Send a status update to both the car and all monitors."""
        payload = json.dumps({"type": state, **extra})
        try:
            await ws.send(payload)
        except Exception:
            pass
        await _broadcast(payload)

    try:
        async for message in ws:
            if isinstance(message, str):
                msg = json.loads(message)
                if msg.get("type") == "wake_word" or "wake_word" in msg:
                    wake_word = msg.get("value") or msg.get("wake_word", wake_word)
                    car_name = msg.get("car_name", "")  # e.g. "小南" or "小北"
                    log_prefix = f"[{car_name}:{car_id}]" if car_name else f"[{car_id}]"
                    # Filter speaker profiles: exclude own TTS voice
                    allowed_profiles = [
                        (n, p) for n, p in _speaker_profiles
                        if n != car_name
                    ]
                    log_prefix = f"[{car_name}:{car_id}]" if car_name else f"[{car_id}]"
                    print(f"{log_prefix} Identified, wake={wake_word}", file=sys.stderr, flush=True)
                    api_key = msg.get("api_key", "")
                    if api_key:
                        global _LLM_API_KEY
                        _LLM_API_KEY = api_key
                        print(f"[{car_id} LLM key received", file=sys.stderr, flush=True)
                    print(f"[{car_id} Wake word: {wake_word}", file=sys.stderr, flush=True)
                continue

            block = np.frombuffer(message, dtype=np.int16).copy()
            if len(block) == 0:
                continue

            pre_buffer.extend(block.tolist())
            level = _rms(block)

            if not speaking and level < max(0.015, noise_floor * 3.0):
                noise_floor = 0.95 * noise_floor + 0.05 * max(level, 0.0005)
            snr_db = 20 * math.log10((level + 1e-8) / (noise_floor + 1e-8))

            energy_hit = snr_db > 8.0 and level > max(0.010, noise_floor * 4.0)
            if energy_hit or speaking:
                vad_window = np.asarray(pre_buffer, dtype=np.float32) / 32768.0
                speech_ts = get_speech_ts(vad_window, silero, threshold=0.35,
                    return_seconds=False, min_speech_duration_ms=MIN_SPEECH_MS,
                    min_silence_duration_ms=SILENCE_GAP_MS)
                vad_hit = bool(speech_ts)
            else:
                vad_hit = False

            voice_start = bool(vad_hit and snr_db > 12.0 and level > max(0.015, noise_floor * 5.0))
            voice_continue = bool(vad_hit and snr_db > 6.0 and level > max(0.008, noise_floor * 3.0))

            # ── vad_status every block for dashboard ──
            state = "speech" if speaking else ("vad_hit" if vad_hit else "silence")
            await _broadcast(json.dumps({
                "type": "vad_status",
                "car_id": car_id,
                "level": round(level, 5),
                "snr_db": round(snr_db, 1),
                "noise_floor": round(noise_floor, 5),
                "vad_hit": bool(vad_hit),
                "energy_hit": bool(energy_hit),
                "speaking": bool(speaking),
                "state": state,
                "uid": uid,
                "silence_blocks": silence_blocks,
            }))

            if not speaking and voice_start:
                speaking = True
                utterance = list(pre_buffer)
                silence_blocks = last_partial = chunk_idx = 0
                await _send_status("speech_start", uid=uid)
                print(f"[{car_id} SPEECH_START uid={uid}", file=sys.stderr, flush=True)

            elif speaking:
                utterance.extend(block.tolist())
                if voice_continue:
                    silence_blocks = 0
                    if len(utterance) - last_partial >= STREAMING_CHUNK_SAMPLES:
                        start = max(0, len(utterance) - STREAMING_CHUNK_SAMPLES)
                        worker.submit(uid, np.asarray(utterance[start:], dtype=np.int16), False, chunk_idx)
                        chunk_idx += 1
                        last_partial = len(utterance)
                else:
                    silence_blocks += 1
                    if silence_blocks * BLOCK_MS >= SILENCE_GAP_MS:
                        samples = np.asarray(utterance, dtype=np.int16)
                        dur_ms = len(samples) * 1000.0 / SAMPLE_RATE
                        if dur_ms >= MIN_SPEECH_MS:
                            worker.submit(uid, samples, True, chunk_idx)
                            # Non-blocking: wait for ASR result in thread pool
                            def _wait_asr():
                                dl = time.monotonic() + 3.0
                                while time.monotonic() < dl:
                                    try:
                                        item = results.get(timeout=0.1)
                                    except queue.Empty:
                                        continue
                                    if item.get("kind") == "final" and item.get("utterance_id") == uid:
                                        return item.get("text", "")
                            loop = asyncio.get_running_loop()
                            text = await loop.run_in_executor(None, _wait_asr)
                            if text and time.monotonic() > tts_mute_until:
                                now = time.monotonic()
                                is_awake = awake_until > now

                                # Exit command — always works regardless of speaker verification
                                if is_awake and _is_exit(text):
                                    await _send_status("command_exit", text=text)
                                    awake_until = 0
                                    tts_mute_until = now + 2.5
                                    print(f"[{car_id} EXIT", file=sys.stderr, flush=True)

                                # Wake word — works for anyone (unverified speakers can wake the car)
                                elif (not is_awake) and wake_word and _fuzzy_pinyin(wake_word) in _fuzzy_pinyin(text):
                                    tts_mute_until = now + 2.5
                                    await _send_status("wake_detected", text=text)
                                    awake_until = now + AWAKE_TIMEOUT
                                    print(f"[{car_id} WAKE", file=sys.stderr, flush=True)

                                else:
                                    # Speaker verification for commands / LLM
                                    allowed = allowed_profiles if allowed_profiles is not None else _speaker_profiles
                                    sim, verified = await loop.run_in_executor(None, _identify_speaker, samples, allowed)
                                    await _broadcast(json.dumps({"type": "speaker_sim", "similarity": round(sim, 4),
                                        "verified": verified, "uid": uid, "car_id": car_id}))
                                    await _send_status("final_text", text=text, uid=uid, speaker_sim=round(sim, 4), speaker_ok=verified)
                                    print(f"[{car_id} FINAL: {text} sim={sim:.3f} ok={verified}", file=sys.stderr, flush=True)
                                    if not verified:
                                        await _send_status("speaker_rejected", similarity=round(sim, 4), threshold=SPEAKER_THRESHOLD, uid=uid)
                                        print(f"[{car_id} REJECTED (sim={sim:.3f}<{SPEAKER_THRESHOLD})", file=sys.stderr, flush=True)
                                    else:
                                        cmd = _parse_command(text)
                                        if is_awake and cmd:
                                            dur = cmd.get("duration", 3.0)
                                            await _send_status("command", cmd=cmd["cmd"], text=text, duration=dur)
                                            print(f"[{car_id} CMD: {cmd['cmd']} dur={dur}s", file=sys.stderr, flush=True)
                                            # Extend awake after command
                                            awake_until = now + AWAKE_TIMEOUT
                                        elif is_awake and len(text.strip()) > 1:
                                            # Not a command — ask LLM
                                            await _send_status("thinking", text=text)
                                            reply = await loop.run_in_executor(None, _ask_llm, text)
                                            if reply:
                                                await _send_status("chat_reply", text=reply, question=text)
                                                print(f"[{car_id} LLM: {reply[:50]}", file=sys.stderr, flush=True)
                                                awake_until = time.monotonic() + AWAKE_TIMEOUT
                                        elif (not is_awake) and wake_word and _fuzzy_pinyin(wake_word) in _fuzzy_pinyin(text):
                                            # Duplicate check for already-awake case — handled above
                                            pass
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
        worker.stop()
        print(f"[{car_id} Car disconnected", file=sys.stderr, flush=True)


# ═══════════════════════════════════════════════════════════════════════
async def dispatch(ws):
    """Route to car or monitor handler based on path."""
    path = ws.request.path if hasattr(ws, 'request') else "/ws/asr"
    if path.endswith("/monitor"):
        await handle_monitor(ws)
    else:
        await handle_car(ws)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"PC ASR  : ws://0.0.0.0:{port}/ws/asr", file=sys.stderr, flush=True)
    print(f"Monitor : ws://0.0.0.0:{port}/ws/monitor", file=sys.stderr, flush=True)
    _load_models()

    async def _serve():
        async with serve(dispatch, "0.0.0.0", port):
            await asyncio.Future()

    asyncio.run(_serve())
