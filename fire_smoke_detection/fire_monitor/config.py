from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _positive_float(name: str, default: str) -> float:
    try:
        value = float(os.environ.get(name, default))
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _positive_int(name: str, default: str, allow_zero: bool = False) -> int:
    try:
        value = int(os.environ.get(name, default))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    minimum = 0 if allow_zero else 1
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


@dataclass(frozen=True)
class FireMonitorConfig:
    root: Path
    ai_base_url: str
    ai_endpoint: str
    ai_api_key: str
    ai_model: str
    ai_timeout_seconds: float
    ai_retries: int
    trigger_window_seconds: float
    trigger_min_hits: int
    event_clear_seconds: float
    review_interval_seconds: float
    evidence_interval_seconds: float
    max_evidence_images: int

    @property
    def runtime_dir(self) -> Path:
        return self.root / "runtime"

    @property
    def evidence_dir(self) -> Path:
        return self.runtime_dir / "evidence"

    @classmethod
    def from_env(cls, root: Path) -> "FireMonitorConfig":
        root = Path(root).resolve()
        load_dotenv(root / ".env")
        base_url = os.environ.get("FIRE_AI_BASE_URL", "https://z.cxwms.com/v1").rstrip("/")
        endpoint = "/" + os.environ.get("FIRE_AI_ENDPOINT", "/chat/completions").strip().lstrip("/")
        return cls(
            root=root,
            ai_base_url=base_url,
            ai_endpoint=endpoint,
            ai_api_key=os.environ.get("FIRE_AI_API_KEY", "").strip(),
            ai_model=os.environ.get("FIRE_AI_MODEL", "gpt-5.4-mini").strip(),
            ai_timeout_seconds=_positive_float("FIRE_AI_TIMEOUT_SECONDS", "30"),
            ai_retries=_positive_int("FIRE_AI_RETRIES", "2", allow_zero=True),
            trigger_window_seconds=_positive_float("FIRE_TRIGGER_WINDOW_SECONDS", "2"),
            trigger_min_hits=_positive_int("FIRE_TRIGGER_MIN_HITS", "5"),
            event_clear_seconds=_positive_float("FIRE_EVENT_CLEAR_SECONDS", "10"),
            review_interval_seconds=_positive_float("FIRE_REVIEW_INTERVAL_SECONDS", "30"),
            evidence_interval_seconds=_positive_float("FIRE_EVIDENCE_INTERVAL_SECONDS", "60"),
            max_evidence_images=_positive_int("FIRE_MAX_EVIDENCE_IMAGES", "10"),
        )
