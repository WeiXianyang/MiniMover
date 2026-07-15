"""Standalone voice service launcher — bypasses broken package imports."""
import sys, os

# ---- config ----
os.environ.setdefault('MINIMOVER_WAKE_WORD', '你好小北')
os.environ.setdefault('MINIMOVER_ASR_BACKEND', 'funasr')
os.environ.setdefault('MINIMOVER_CAR_URL', 'http://127.0.0.1:5000')

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # MiniMover root
VOICE = os.path.join(PROJECT, 'voice_assistant')
sys.path.insert(0, PROJECT)
sys.path.insert(0, VOICE)

# ---- manual imports (avoid broken relative imports) ----
import importlib

def _load(modname):
    return importlib.import_module(modname)

# Load config first
config_mod = _load('config')
config = config_mod.VoiceConfig()

# Choose wake word (env overrides)
wake_word = os.environ.get('MINIMOVER_WAKE_WORD', config.wake_word)
print(f"WAKE: {wake_word}")

# ASR backend
asr_mod = _load('asr_backend')
asr_backend = asr_mod.FunAsrBackend(
    sample_rate=config.sample_rate,
    silence_ms=config.silence_ms,
    vad_threshold=config.vad_threshold,
)

# TTS backend
tts_mod = _load('tts_backend')
car_mod = _load('car_client')
car = car_mod.CarClient(base_url=os.environ.get('MINIMOVER_CAR_URL', 'http://127.0.0.1:5000'))
tts = tts_mod.CarTtsBackend(car, lang='zh')

# Wake word service
wake_mod = _load('wake_word')
service = wake_mod.WakeWordVoiceService(
    car,
    asr_backend=asr_backend,
    tts_backend=tts,
    wake_word=wake_word,
    wake_greeting=os.environ.get('MINIMOVER_WAKE_GREETING', f'你好，我是{wake_word[2:]}，有什么可以帮你的？') if wake_word else '',
    idle_timeout=float(os.environ.get('MINIMOVER_WAKE_TIMEOUT', '30')),
)

print("STARTING...")
service.run()
