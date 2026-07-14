#!/usr/bin/env python3
"""iCar 音频驱动 —— 录音 / 播放 / TTS
硬件:
  麦克风: hw:2,0  (讯飞 XFM-DP-V0.0.18, mono 16kHz)
  扬声器: PulseAudio USB Sink (C-Media USB Audio, stereo 44.1kHz)
TTS:
  主力: 阿里云百炼 CosyVoice (DashScope API)
  回退: espeak-ng
"""

import os
import io
import json
import subprocess
import threading
import time
import uuid
import wave
import tempfile
from pathlib import Path

# === 配置 ===
MIC_DEVICE = "hw:2,0"       # 讯飞麦克风阵列
USB_SINK = "alsa_output.usb-C-Media_Electronics_Inc._USB_Audio_Device-00.analog-stereo"
RECORD_DIR = Path("/tmp/icar_audio")
RECORD_DIR.mkdir(parents=True, exist_ok=True)

# TTS 环境变量加载（从小车 ~/MiniMover/.tts.env）
_ENV_LOADED = False

def _load_tts_env():
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    env_file = Path(__file__).resolve().parent.parent / ".tts.env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("export ") and "=" in line:
                k, v = line[len("export "):].split("=", 1)
                v = v.strip().strip('"').strip("'")
                if k not in os.environ:
                    os.environ[k] = v
    _ENV_LOADED = True

# === 录音管理 ===
class _Recorder:
    """单例录音状态机: idle -> recording -> done"""
    def __init__(self):
        self._proc = None
        self._filepath = ""
        self._start_time = 0.0
        self._lock = threading.Lock()
        self._timer = None
        self._status = "idle"  # idle | recording | done

    def start(self, duration_sec: float = 0) -> str:
        """
        启动录音, 返回 record_id (不含后缀的文件名)。
        duration_sec=0 表示手动停止; >0 表示定时录音。
        """
        with self._lock:
            if self._status == "recording":
                raise RuntimeError("已在录音中")
            rid = uuid.uuid4().hex[:12]
            wav_path = str(RECORD_DIR / f"{rid}.wav")
            # arecord 参数: -D 设备 -f 格式 -r 采样率 -c 声道
            cmd = ["arecord", "-D", MIC_DEVICE,
                   "-f", "S16_LE", "-r", "16000", "-c", "1",
                   "-q", wav_path]
            self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL)
            self._filepath = wav_path
            self._start_time = time.time()
            self._status = "recording"
            rid_out = rid

        if duration_sec > 0:
            self._timer = threading.Timer(duration_sec, self.stop)
            self._timer.start()

        return rid_out

    def status(self) -> dict:
        with self._lock:
            elapsed = (time.time() - self._start_time) if self._status == "recording" else 0
            return {"status": self._status, "elapsed": round(elapsed, 1)}

    def stop(self) -> str:
        """停止录音, 返回 wav 文件路径"""
        with self._lock:
            if self._status != "recording":
                if self._status == "done" and self._filepath:
                    return self._filepath
                raise RuntimeError("没有正在进行的录音")
            if self._timer:
                self._timer.cancel()
                self._timer = None
            proc = self._proc
            self._status = "done"
        # 在锁外等待进程结束, 避免阻塞
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        return self._filepath

    def get_wav(self) -> bytes:
        """返回最近一次录音的 WAV 字节"""
        with self._lock:
            if self._status != "done" or not self._filepath:
                raise RuntimeError("没有可用的录音")
            return Path(self._filepath).read_bytes()


_recorder = _Recorder()


# === 播放管理 ===
class _Player:
    """单例播放状态机"""
    def __init__(self):
        self._proc = None
        self._lock = threading.Lock()
        self._status = "idle"

    def play(self, wav_data: bytes) -> None:
        self.stop()
        # paplay 直接指定 PulseAudio sink, 绕过默认 sink 问题
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(wav_data)
        tmp.close()
        with self._lock:
            self._proc = subprocess.Popen(
                ["paplay", "--device=" + USB_SINK, tmp.name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._status = "playing"
        def _cleanup():
            self._proc.wait()
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
        threading.Thread(target=_cleanup, daemon=True).start()

    def play_file(self, filepath: str) -> None:
        self.stop()
        with self._lock:
            self._proc = subprocess.Popen(
                ["paplay", "--device=" + USB_SINK, filepath],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._status = "playing"

    def stop(self) -> None:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
            self._status = "idle"

    @property
    def status(self) -> str:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                return "playing"
            return "idle"


_player = _Player()


# === TTS ===

DASHSCOPE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2speech/speech-synthesis"

def _dashscope_tts(text: str, voice: str = "longanyang", model: str = "cosyvoice-v3-flash") -> bytes:
    """调用阿里云百炼 CosyVoice, 返回 WAV 字节。失败抛异常。"""
    import requests
    _load_tts_env()
    api_key = os.environ.get("MINIMOVER_DASHSCOPE_API_KEY", "")
    if not api_key:
        raise RuntimeError("MINIMOVER_DASHSCOPE_API_KEY not set")
    v = os.environ.get("MINIMOVER_COSYVOICE_VOICE", voice)
    m = os.environ.get("MINIMOVER_COSYVOICE_MODEL", model)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": m,
        "input": {"text": text, "voice": v},
        "parameters": {"format": "wav", "sample_rate": 24000},
    }
    r = requests.post(DASHSCOPE_URL, json=payload, headers=headers, timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"DashScope HTTP {r.status_code}: {r.text[:200]}")
    # DashScope 返回 JSON, audio 字段是 WAV base64
    resp = r.json()
    audio_b64 = resp.get("output", {}).get("audio", "")
    if not audio_b64:
        raise RuntimeError(f"DashScope response missing audio: {json.dumps(resp, ensure_ascii=False)[:200]}")
    import base64
    return base64.b64decode(audio_b64)


def _has_espeak() -> bool:
    return subprocess.call(["which", "espeak-ng"],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL) == 0


def say(text: str, lang: str = "zh") -> bytes:
    """
    TTS 文本转语音, 返回 WAV 字节。
    优先 DashScope CosyVoice, 不可用时回退 espeak-ng。
    """
    _player.stop()
    try:
        return _dashscope_tts(text)
    except Exception as e:
        print(f"[TTS] DashScope failed: {e}, falling back to espeak-ng")
    # 回退离线 TTS
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name
    try:
        espeak = "espeak-ng" if _has_espeak() else "espeak"
        lang_map = {"zh": "cmn", "en": "en", "ja": "ja"}
        voice = lang_map.get(lang, lang)
        subprocess.run([espeak, "-w", wav_path, "-v", voice,
                        "-s", "150", text],
                       check=True, capture_output=True, timeout=10)
        return Path(wav_path).read_bytes()
    finally:
        if os.path.exists(wav_path):
            os.unlink(wav_path)


def play_say(text: str, lang: str = "zh") -> None:
    """TTS + 直接播放"""
    wav = say(text, lang)
    _player.play(wav)


# === 设备信息 ===
def get_devices() -> dict:
    """返回音频设备信息"""
    _load_tts_env()
    tts_provider = os.environ.get("MINIMOVER_TTS_PROVIDER", "dashscope")
    return {
        "mic": {
            "device": MIC_DEVICE,
            "name": "iFlytek XFM-DP-V0.0.18",
            "rate": 16000,
            "channels": 1,
            "format": "S16_LE"
        },
        "speaker": {
            "device": USB_SINK,
            "name": "C-Media USB Audio (paplay)",
            "rate": 44100,
            "channels": 2
        },
        "tts": {
            "available": True,
            "engine": "DashScope CosyVoice" if tts_provider == "dashscope" else "espeak-ng",
            "provider": tts_provider,
        }
    }


# === 公开 API ===
def record_start(duration_sec: float = 0) -> str:
    """开始录音, 返回 record_id"""
    return _recorder.start(duration_sec)


def record_status() -> dict:
    return _recorder.status()


def record_stop() -> tuple:
    """停止录音, 返回 (record_id, wav_bytes)"""
    path = _recorder.stop()
    rid = Path(path).stem
    wav_bytes = Path(path).read_bytes()
    return rid, wav_bytes


def record_get(record_id: str) -> bytes:
    """获取指定录音的 WAV 数据"""
    wav_path = RECORD_DIR / f"{record_id}.wav"
    if not wav_path.exists():
        raise FileNotFoundError(f"录音 {record_id} 不存在")
    return wav_path.read_bytes()


def play_wav(wav_data: bytes) -> None:
    """播放 WAV 字节流"""
    _player.play(wav_data)


def play_file(filepath: str) -> None:
    """播放 WAV 文件"""
    _player.play_file(filepath)


def stop_playback() -> None:
    _player.stop()


# ===== 测试入口 =====
if __name__ == "__main__":
    print("=== iCar 音频驱动测试 ===")
    print("设备:", get_devices())

    print("\n--- 录音测试 (3秒) ---")
    rid = record_start(duration_sec=3)
    print(f"录音 ID: {rid}")
    while record_status()["status"] == "recording":
        time.sleep(0.3)
    rid2, wav_data = record_stop()
    print(f"录音完成: {rid2}, 大小 {len(wav_data)} bytes")

    print("\n--- 播放测试 ---")
    if len(wav_data) > 0:
        play_wav(wav_data)
        time.sleep(1)
        stop_playback()
        print("播放完毕")