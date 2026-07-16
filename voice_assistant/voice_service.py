"""Standalone first-version voice control service."""

import argparse
import logging
import random
import threading
import time

try:
    from .asr_backend import FunAsrBackend, WhisperBackend
    from .remote_audio_backend import RemoteWhisperBackend
    from .config import VoiceConfig
    from .llm_client import LlmClient
    from .tts_backend import CarTtsBackend, HttpTtsBackend
    from .speaker_verifier import SpeakerVerifier
    from .car_client import CarClient
    from .command_parser import parse_command
    from .wake_word import WakeWordVoiceService
    from .hospital_guide import HospitalGuideConfig, HospitalGuideOrchestrator
    from .medical_knowledge import MedicalKnowledgeBase
except ImportError:
    from asr_backend import FunAsrBackend, WhisperBackend
    from remote_audio_backend import RemoteWhisperBackend
    from config import VoiceConfig
    from llm_client import LlmClient
    from tts_backend import CarTtsBackend, HttpTtsBackend
    from speaker_verifier import SpeakerVerifier
    from car_client import CarClient
    from command_parser import parse_command
    from wake_word import WakeWordVoiceService
    from hospital_guide import HospitalGuideConfig, HospitalGuideOrchestrator
    from medical_knowledge import MedicalKnowledgeBase

LOGGER = logging.getLogger("mini-mover-voice")


class VoiceService:
    def __init__(self, car_client, asr_backend, speed=35, duration=0.8, llm_client=None, tts_backend=None, speaker_verifier=None, hospital_guide=None):
        self.car_client = car_client
        self.asr_backend = asr_backend
        self.speed = speed
        self.duration = duration
        self.llm_client = llm_client
        self.tts_backend = tts_backend
        self.speaker_verifier = speaker_verifier
        self.hospital_guide = hospital_guide
        self.stop_event = threading.Event()
        self.last_command = None
        self.last_command_at = 0.0

    def handle_final(self, event):
        text = event.get("text", "")
        command = parse_command(text)
        if command is None:
            try:
                if self.hospital_guide:
                    answer = self.hospital_guide.handle(text)
                elif self.llm_client:
                    answer = self.llm_client.answer(text)
                else:
                    LOGGER.info("ignored unsupported speech: %s", text)
                    return
                LOGGER.info("answer: %s", answer)
                if self.tts_backend and answer:
                    self.tts_backend.speak(answer)
            except Exception:
                LOGGER.exception("question handling failed for %r", text)
            return
        if command["cmd"] == "stop":
            self.car_client.execute(command, self.speed, 0)
            LOGGER.info("emergency stop from %r", text)
            return
        if self.speaker_verifier:
            samples = event.get("samples")
            if samples is None:
                LOGGER.warning("motion command denied: no audio samples for speaker verification")
                return
            try:
                verification = self.speaker_verifier.verify(samples)
            except Exception:
                LOGGER.exception("speaker verification failed")
                return
            if not verification.get("verified"):
                LOGGER.warning("motion command denied by speaker gate: %s", verification)
                return
        now = time.monotonic()
        if command["cmd"] == self.last_command and now - self.last_command_at < 0.5:
            LOGGER.info("duplicate command suppressed: %s", command["cmd"])
            return
        self.last_command = command["cmd"]
        self.last_command_at = now
        # ---- dance: special handling (TTS + motion in parallel) ----
        if command["cmd"] == "dance":
            _DANCE_LINES = [
                "来啦来啦，看我扭一扭！咚咚锵咚咚锵~",
                "音乐响起来，屁股扭起来，左三圈右三圈~",
                "今天心情好，给你跳个舞！虽然我只有轮子，但我有灵魂！",
                "旋转跳跃我闭着眼，尘嚣看不见你沉醉了没~",
                "我是小可爱，也是小霸王，扭起来谁都挡不住！",
                "蹦瞎卡拉卡！蹦瞎卡拉卡！",
            ]
            say = random.choice(_DANCE_LINES)
            LOGGER.info("dance: %s", say)
            if self.tts_backend:
                threading.Thread(target=self.tts_backend.speak, args=(say,), daemon=True).start()
            try:
                self.car_client.execute_dance()
                LOGGER.info("dance sequence started from %r", text)
            except Exception:
                LOGGER.exception("dance command failed for %r", text)
            return
        # ---- normal motion command ----
        try:
            result = self.car_client.execute(command, self.speed, self.duration)
            LOGGER.info("executed %s from %r: %s", command["cmd"], text, result)
        except Exception:
            LOGGER.exception("car command failed for %r", text)

    def reset_conversation(self):
        if self.hospital_guide:
            self.hospital_guide.reset()

    def handle_partial(self, event):
        LOGGER.debug("partial: %s", event.get("text", ""))

    def run(self):
        LOGGER.info("voice service started")
        self.asr_backend.run(self.handle_final, self.handle_partial, self.stop_event)

    def stop(self):
        self.stop_event.set()
        try:
            self.car_client.execute({"cmd": "stop"}, self.speed, 0)
        except Exception:
            LOGGER.exception("failed to stop car during service shutdown")
        if self.tts_backend:
            self.tts_backend.stop()


def main():
    parser = argparse.ArgumentParser(description="MiniMover voice control")
    config = VoiceConfig()
    parser.add_argument("--car-url", default=config.car_url)
    parser.add_argument("--asr", choices=("auto", "funasr", "whisper", "remote_whisper"), default=config.asr_backend)
    parser.add_argument("--speed", type=int, default=config.speed)
    parser.add_argument("--duration", type=float, default=config.duration)
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--speaker-profile", default="")
    parser.add_argument("--speaker-threshold", type=float, default=0.38)
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")
    asr = FunAsrBackend()
    if args.asr == "remote_whisper":
        asr = RemoteWhisperBackend(config.car_url, config.whisper_url, config.api_key, config.whisper_model, config.car_audio_duration)
    elif args.asr == "whisper":
        asr = WhisperBackend(config.whisper_url, config.api_key, config.whisper_model)
    elif args.asr == "auto":
        LOGGER.info("using FunASR primary backend; use --asr whisper for network fallback")
    llm = LlmClient(config.llm_url, config.api_key, config.llm_model) if config.llm_url else None
    if config.car_speaker:
        tts = CarTtsBackend(config.car_url)
    else:
        tts = HttpTtsBackend(config.tts_url, config.api_key, config.tts_voice) if config.tts_url else None
    speaker = SpeakerVerifier(args.speaker_profile, args.speaker_threshold) if args.speaker_profile else None
    if speaker and not speaker.enrolled:
        raise SystemExit("speaker profile does not exist; enroll it first")
    # ---- ready notification ----
    if tts and config.wake_word:
        def _notify_ready():
            try:
                tts.speak("准备就绪")
            except Exception:
                pass
        asr._on_ready = _notify_ready

    car_client = CarClient(args.car_url)
    hospital_guide = None
    if config.hospital_guide_enabled:
        try:
            hospital_guide = HospitalGuideOrchestrator(
                HospitalGuideConfig.from_path(config.hospital_guide_path),
                MedicalKnowledgeBase.from_jsonl(config.medical_kb_path),
                llm,
                car_client,
                memory_turns=config.medical_memory_turns,
                retrieval_limit=config.medical_retrieval_limit,
                reply_max_chars=config.medical_reply_max_chars,
            )
            LOGGER.info("hospital guide enabled with configuration: %s", config.hospital_guide_path)
        except ValueError:
            LOGGER.exception("hospital guide disabled because its configuration is invalid")

    service = VoiceService(
        car_client, asr, args.speed, args.duration, llm, tts, speaker, hospital_guide
    )

    # ---- wake-word gate ----
    if config.wake_word:
        service = WakeWordVoiceService(
            service,
            wake_word=config.wake_word,
            greeting=config.wake_greeting,
            idle_timeout=config.wake_idle_timeout,
        )
        LOGGER.info("wake-word mode: %r", config.wake_word)

    try:
        service.run()
    except KeyboardInterrupt:
        service.stop()


if __name__ == "__main__":
    main()
