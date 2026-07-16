"""Wake-word gated voice service.

The service listens continuously through the ASR backend. While in IDLE state it
scans every final utterance for the configured wake word. Once woken it greets
the user and passes subsequent utterances to the normal VoiceService handler
for a configurable time window.
"""

import logging
import threading
import time

LOGGER = logging.getLogger("mini-mover-voice")


class WakeWordVoiceService:
    """Wrap a VoiceService with a wake-word gate and greeting."""

    def __init__(
        self,
        voice_service,
        *,
        wake_word="",
        greeting="",
        idle_timeout=30.0,
    ):
        if not wake_word:
            raise ValueError("wake_word is required")
        self._wake_word = wake_word
        self._greeting = greeting or f"\u4f60\u597d\uff0c\u6211\u662f{wake_word}\uff0c\u6709\u4ec0\u4e48\u53ef\u4ee5\u5e2e\u4f60\u7684\uff1f"
        self._idle_timeout = idle_timeout
        self._voice = voice_service
        self._awake = False
        self._last_awake_at = 0.0
        self._lock = threading.Lock()

    @property
    def awake(self):
        with self._lock:
            return self._awake

    def run(self):
        LOGGER.info(
            "wake-word service started (wake_word=%r, timeout=%.0fs)",
            self._wake_word,
            self._idle_timeout,
        )
        self._voice.asr_backend.run(
            on_final=self._on_final,
            on_partial=self._voice.handle_partial,
            stop_event=self._voice.stop_event,
        )

    def stop(self):
        self._voice.stop()

    def _on_final(self, event):
        text = (event.get("text") or "").strip()
        now = time.monotonic()
        should_reset = False
        should_greet = False
        should_delegate = False

        with self._lock:
            if not self._awake:
                if self._wake_word in text:
                    self._awake = True
                    self._last_awake_at = now
                    should_reset = True
                    should_greet = True
                    LOGGER.info("woken by wake-word %r in: %s", self._wake_word, text)
            elif now - self._last_awake_at > self._idle_timeout:
                self._awake = False
                should_reset = True
                LOGGER.info("wake window expired, back to idle")
            elif text:
                self._last_awake_at = now
                should_delegate = True

        if should_reset:
            self._reset_conversation()
        if should_greet:
            self._say_greeting()
        if should_delegate:
            self._voice.handle_final(event)

    def _reset_conversation(self):
        reset = getattr(self._voice, "reset_conversation", None)
        if callable(reset):
            reset()

    def _say_greeting(self):
        tts = getattr(self._voice, "tts_backend", None)
        if tts is None:
            LOGGER.warning("no TTS backend \u2013 greeting suppressed")
            return
        try:
            tts.speak(self._greeting)
        except Exception:
            LOGGER.exception("greeting TTS failed")
