"""Environment-backed configuration for the voice assistant."""

import os


def _float(name, default):
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class VoiceConfig:
    def __init__(self):
        self.asr_backend = os.getenv("MINIMOVER_ASR_BACKEND", "auto").lower()
        self.car_url = os.getenv("MINIMOVER_CAR_URL", "http://127.0.0.1:5000")
        self.car_audio_duration = _float("MINIMOVER_CAR_AUDIO_DURATION", 4.0)
        self.speed = _int("MINIMOVER_VOICE_SPEED", 35)
        self.duration = _float("MINIMOVER_VOICE_DURATION", 0.8)
        self.whisper_url = os.getenv("MINIMOVER_WHISPER_URL", "")
        self.whisper_model = os.getenv("MINIMOVER_WHISPER_MODEL", "whisper-1")
        self.llm_url = os.getenv("MINIMOVER_LLM_URL", "")
        self.llm_model = os.getenv("MINIMOVER_LLM_MODEL", "")
        self.api_key = os.getenv("MINIMOVER_API_KEY", "")
        self.tts_url = os.getenv("MINIMOVER_TTS_URL", "")
        self.tts_voice = os.getenv("MINIMOVER_TTS_VOICE", "alloy")
        self.tts_command = os.getenv("MINIMOVER_TTS_COMMAND", "aplay -q -")
        self.car_speaker = os.getenv("MINIMOVER_CAR_SPEAKER", "0").lower() in {"1", "true", "yes", "on"}

        # ---- wake-word configuration ----
        self.wake_word = os.getenv("MINIMOVER_WAKE_WORD", "")
        self.wake_greeting = os.getenv("MINIMOVER_WAKE_GREETING", "")
        self.wake_idle_timeout = _float("MINIMOVER_WAKE_TIMEOUT", 30.0)
