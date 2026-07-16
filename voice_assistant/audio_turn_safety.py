"""Pure audio helpers shared by the car client, ASR relay, and API server."""

from __future__ import annotations

import io
import math
import threading
import time
import wave
from collections.abc import Callable, Sequence


class CaptureGate:
    """Suppress microphone frames for the whole playback turn plus a tail.

    The gate is reference counted so overlapping playback requests cannot
    accidentally re-enable capture before the final speaker output ends.
    """

    def __init__(
        self,
        post_playback_ms: int = 650,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._post_playback_s = max(0, post_playback_ms) / 1000.0
        self._clock = clock
        self._active_playbacks = 0
        self._generation = 0
        self._muted_until = 0.0
        self._lock = threading.Lock()

    def begin_playback(self) -> bool:
        """Start a playback turn and return whether capture just became muted."""
        with self._lock:
            was_idle = self._active_playbacks == 0
            self._active_playbacks += 1
            self._generation += 1
            self._muted_until = math.inf
            return was_idle

    def finish_playback(self, duration_ms: int | float = 0) -> tuple[float, int] | None:
        """Finish one playback and return final mute time and generation, if last."""
        duration_s = max(0.0, float(duration_ms) / 1000.0)
        with self._lock:
            if self._active_playbacks > 0:
                self._active_playbacks -= 1
            if self._active_playbacks != 0:
                return None
            mute_s = duration_s + self._post_playback_s
            self._muted_until = self._clock() + mute_s
            return mute_s, self._generation

    def can_release_capture(self, generation: int) -> bool:
        """Return true only if no newer playback began during the mute tail."""
        with self._lock:
            return self._active_playbacks == 0 and self._generation == generation

    def is_muted(self) -> bool:
        with self._lock:
            return self._active_playbacks > 0 or self._clock() < self._muted_until


def normalized_rms(samples: Sequence[int]) -> float:
    """Return RMS for signed 16-bit PCM in a stable 0..1 scale."""
    if not samples:
        return 0.0
    squared_mean = sum(float(sample) * float(sample) for sample in samples) / len(samples)
    return math.sqrt(squared_mean) / 32768.0


def wav_duration_ms(wav_data: bytes) -> int:
    """Return WAV duration in milliseconds, rejecting malformed audio."""
    with wave.open(io.BytesIO(wav_data), "rb") as wav_file:
        frame_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
    if frame_rate <= 0:
        raise ValueError("WAV sample rate must be positive")
    return round(frame_count * 1000 / frame_rate)
