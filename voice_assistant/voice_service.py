"""Standalone first-version voice control service."""

import argparse
import logging
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
except ImportError:
    from asr_backend import FunAsrBackend, WhisperBackend
    from remote_audio_backend import RemoteWhisperBackend
    from config import VoiceConfig
    from llm_client import LlmClient
    from tts_backend import CarTtsBackend, HttpTtsBackend
    from speaker_verifier import SpeakerVerifier
    from car_client import CarClient
    from command_parser import parse_command

LOGGER = logging.getLogger("mini-mover-voice")


class VoiceService:
    def __init__(self, car_client, asr_backend, speed=35, duration=0.8, llm_client=None, tts_backend=None, speaker_verifier=None):
        self.car_client = car_client
        self.asr_backend = asr_backend
        self.speed = speed
        self.duration = duration
        self.llm_client = llm_client
        self.tts_backend = tts_backend
        self.speaker_verifier = speaker_verifier
        self.stop_event = threading.Event()
        self.last_command = None
        self.last_command_at = 0.0

    def handle_final(self, event):
        text = event.get("text", "")
        command = parse_command(text)
        if command is None:
            if not self.llm_client:
                LOGGER.info("ignored unsupported speech: %s", text)
                return
            try:
                answer = self.llm_client.answer(text)
                LOGGER.info("answer: %s", answer)
                if self.tts_backend:
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
        try:
            result = self.car_client.execute(command, self.speed, self.duration)
            LOGGER.info("executed %s from %r: %s", command["cmd"], text, result)
        except Exception:
            LOGGER.exception("car command failed for %r", text)

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
    service = VoiceService(CarClient(args.car_url), asr, args.speed, args.duration, llm, tts, speaker)
    try:
        service.run()
    except KeyboardInterrupt:
        service.stop()


if __name__ == "__main__":
    main()
