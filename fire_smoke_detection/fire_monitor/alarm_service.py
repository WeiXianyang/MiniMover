from __future__ import annotations

import json
import logging
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Protocol

from .types import AlarmEvent


class AlarmService(Protocol):
    def report_confirmed_fire(self, event: AlarmEvent) -> bool: ...
    def report_suspected_smoke(self, event: AlarmEvent) -> bool: ...
    def report_ai_unavailable(self, event: AlarmEvent) -> bool: ...


class LoggingAlarmService:
    def __init__(self, runtime_dir: Path, logger: logging.Logger):
        self.runtime_dir = Path(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger
        self._sent = set()
        self._lock = threading.Lock()

    def report_confirmed_fire(self, event: AlarmEvent) -> bool:
        return self._report(event, "【火灾报警】AI确认发现明火")

    def report_suspected_smoke(self, event: AlarmEvent) -> bool:
        return self._report(event, "【烟雾报警】AI确认发现疑似火灾烟雾")

    def report_ai_unavailable(self, event: AlarmEvent) -> bool:
        return self._report(event, "【系统报警】AI服务失效，需人工介入")

    def _report(self, event: AlarmEvent, message: str) -> bool:
        key = (event.event_id, event.alarm_type)
        with self._lock:
            if key in self._sent:
                return False
            self._sent.add(key)
            payload = {
                "event_id": event.event_id, "alarm_type": event.alarm_type,
                "occurred_at": event.occurred_at.isoformat(), "reason": event.reason,
                "confidence": event.confidence, "evidence_path": event.evidence_path,
                "local_detection_gone": event.local_detection_gone,
            }
            with (self.runtime_dir / "alarms.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
                stream.flush()
        self.logger.error("%s event=%s reason=%s", message, event.event_id, event.reason)
        return True


def configure_monitor_logger(runtime_dir: Path) -> logging.Logger:
    runtime_dir = Path(runtime_dir); runtime_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("fire_monitor")
    logger.setLevel(logging.INFO); logger.propagate = False
    if getattr(logger, "_fire_monitor_configured", False):
        return logger
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = RotatingFileHandler(runtime_dir / "fire_monitor.log", maxBytes=1024*1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter); logger.addHandler(file_handler)
    console = logging.StreamHandler(); console.setFormatter(formatter); logger.addHandler(console)
    logger._fire_monitor_configured = True
    return logger
