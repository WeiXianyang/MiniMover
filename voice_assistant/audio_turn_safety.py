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


def _received_wav_data_size(wav_data: bytes) -> int:
    """Return the data bytes actually present, not an untrusted RIFF length."""
    if len(wav_data) < 12 or wav_data[:4] != b"RIFF" or wav_data[8:12] != b"WAVE":
        raise ValueError("invalid WAV header")

    offset = 12
    while offset + 8 <= len(wav_data):
        chunk_id = wav_data[offset:offset + 4]
        declared_size = int.from_bytes(wav_data[offset + 4:offset + 8], "little")
        data_offset = offset + 8
        available_size = len(wav_data) - data_offset
        if chunk_id == b"data":
            # DashScope streaming WAV responses use 0xFFFFFFFF as a placeholder
            # here; cap it at the bytes that were actually received.
            return min(declared_size, available_size)

        next_offset = data_offset + declared_size + (declared_size & 1)
        if next_offset > len(wav_data):
            raise ValueError("truncated WAV chunk")
        offset = next_offset

    raise ValueError("WAV data chunk is missing")


def wav_duration_ms(wav_data: bytes) -> int:
    """Return WAV duration using the PCM bytes actually received."""
    with wave.open(io.BytesIO(wav_data), "rb") as wav_file:
        frame_rate = wav_file.getframerate()
        bytes_per_frame = wav_file.getnchannels() * wav_file.getsampwidth()
    if frame_rate <= 0:
        raise ValueError("WAV sample rate must be positive")
    if bytes_per_frame <= 0:
        raise ValueError("WAV frame width must be positive")
    frame_count = _received_wav_data_size(wav_data) // bytes_per_frame
    return round(frame_count * 1000 / frame_rate)