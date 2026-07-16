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
        module_dir = os.path.dirname(os.path.abspath(__file__))
        default_guide_path = os.path.join(module_dir, "data", "hospital_guide_template.json")
        default_kb_path = os.path.join(module_dir, "data", "shortmedkg", "input_v4.jsonl")
        default_telemetry_path = os.path.join(module_dir, "data", "hospital_guide_runtime.json")

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

        self.hospital_guide_enabled = os.getenv(
            "MINIMOVER_HOSPITAL_GUIDE_ENABLED", "1"
        ).lower() not in {"0", "false", "no", "off"}
        self.hospital_guide_path = os.getenv(
            "MINIMOVER_HOSPITAL_GUIDE_PATH", default_guide_path
        )
        self.medical_kb_path = os.getenv("MINIMOVER_MEDICAL_KB_PATH", default_kb_path)
        self.hospital_guide_telemetry_path = os.getenv(
            "MINIMOVER_HOSPITAL_GUIDE_TELEMETRY_PATH", default_telemetry_path
        )
        self.medical_memory_turns = max(
            1, min(_int("MINIMOVER_MEDICAL_MEMORY_TURNS", 6), 12)
        )
        self.medical_retrieval_limit = max(
            1, min(_int("MINIMOVER_MEDICAL_RETRIEVAL_LIMIT", 3), 5)
        )
        self.medical_reply_max_chars = max(
            60, min(_int("MINIMOVER_MEDICAL_REPLY_MAX_CHARS", 180), 300)
        )

        # ---- wake-word configuration ----
        self.wake_word = os.getenv("MINIMOVER_WAKE_WORD", "")
        self.wake_greeting = os.getenv("MINIMOVER_WAKE_GREETING", "")
        self.wake_idle_timeout = _float("MINIMOVER_WAKE_TIMEOUT", 30.0)
