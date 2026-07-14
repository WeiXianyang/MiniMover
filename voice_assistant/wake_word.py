"""Wake-word gated voice service.

The service listens continuously through the ASR backend.  While in IDLE
state it scans every final utterance for the configured wake word (e.g.
"你好小南").  Once woken it greets the user via TTS, then passes subsequent
utterances through to the normal VoiceService handler for a configurable
time window.  After the window expires (or on an explicit stop command) it
falls back to IDLE.
"""

import logging
import threading
import time

LOGGER = logging.getLogger("mini-mover-voice")


class WakeWordVoiceService:
    """Wraps a VoiceService with a wake-word gate and greeting."""

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
        self._greeting = greeting or f"你好，我是{wake_word}，有什么可以帮你的？"
        self._idle_timeout = idle_timeout
        self._voice = voice_service
        self._awake = False
        self._last_awake_at = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def awake(self):
        with self._lock:
            return self._awake

    def run(self):
        LOGGER.info("wake-word service started (wake_word=%r, timeout=%.0fs)",
                    self._wake_word, self._idle_timeout)
        self._voice.asr_backend.run(
            on_final=self._on_final,
            on_partial=self._voice.handle_partial,
            stop_event=self._voice.stop_event,
        )

    def stop(self):
        self._voice.stop()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_final(self, event):
        text = (event.get("text") or "").strip()
        now = time.monotonic()

        with self._lock:
            if not self._awake:
                # ----- IDLE: scan for wake word -------------------------------
                if self._wake_word in text:
                    self._awake = True
                    self._last_awake_at = now
                    LOGGER.info("⏰ woken by wake-word %r in: %s", self._wake_word, text)
                    self._say_greeting()
                return

            # ----- AWAKE: check timeout ---------------------------------------
            if now - self._last_awake_at > self._idle_timeout:
                self._awake = False
                LOGGER.info("⏰ wake window expired, back to idle")
                return

        # ----- AWAKE: delegate to normal handler -------------------------
        if text:
            self._last_awake_at = now
            self._voice.handle_final(event)

    def _say_greeting(self):
        tts = getattr(self._voice, "tts_backend", None)
        if tts is None:
            LOGGER.warning("no TTS backend – greeting suppressed")
            return
        try:
            tts.speak(self._greeting)
        except Exception:
            LOGGER.exception("greeting TTS failed")
