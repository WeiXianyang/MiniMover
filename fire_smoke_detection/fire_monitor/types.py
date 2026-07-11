from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple


class EventState(str, Enum):
    IDLE = "idle"
    AI_REVIEWING = "ai_reviewing"
    AI_REJECTED = "ai_rejected"
    ALARMED_FIRE = "alarmed_fire"
    ALARMED_SMOKE = "alarmed_smoke"
    AI_FAILED = "ai_failed"


class AIResultKind(str, Enum):
    CONFIRMED_FIRE = "confirmed_fire"
    SUSPECTED_SMOKE = "suspected_smoke"
    NO_FIRE = "no_fire"


@dataclass(frozen=True)
class Detection:
    class_name: str
    confidence: float


@dataclass(frozen=True)
class AIReviewRequest:
    event_id: str
    review_id: int
    jpeg_bytes: bytes
    captured_at: datetime


@dataclass(frozen=True)
class AIReviewResult:
    event_id: str
    review_id: int
    success: bool
    attempts: int
    result: Optional[AIResultKind] = None
    confidence: Optional[float] = None
    reason: str = ""
    error: str = ""


@dataclass(frozen=True)
class AlarmEvent:
    event_id: str
    alarm_type: str
    occurred_at: datetime
    reason: str
    confidence: Optional[float]
    evidence_path: Optional[str]
    local_detection_gone: bool


FIRE_CLASSES: Tuple[str, ...] = ("fire", "smoke")
