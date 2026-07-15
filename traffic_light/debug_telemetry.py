#!/usr/bin/env python3
"""Lightweight debug telemetry shared by traffic_light detectors and their monitor windows."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

_SENSITIVE = ("key", "authorization", "token", "secret")


def _merge(current: dict, changes: dict) -> dict:
    merged = dict(current)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _validate(payload: dict) -> None:
    for key, value in payload.items():
        if any(word in key.lower() for word in _SENSITIVE):
            raise ValueError(f"sensitive debug field is not allowed: {key}")
        if isinstance(value, dict):
            _validate(value)


class NullTelemetry:
    enabled = False

    def update(self, **changes) -> None: pass
    def event(self, stage: str, detail: str, **fields) -> None: pass
    def write_image(self, name: str, frame) -> None: pass
    def write_jpeg_bytes(self, name: str, data: bytes) -> None: pass


class DebugTelemetry:
    enabled = True

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._status: dict[str, Any] = {}
        self._lock = threading.RLock()
        self.last_error = ""

    def reset(self) -> None:
        with self._lock:
            for name in ("status.json", "events.jsonl", "latest_frame.jpg"):
                (self.root / name).unlink(missing_ok=True)
            self._status = {}

    def update(self, **changes) -> None:
        _validate(changes)
        with self._lock:
            self._status = _merge(self._status, changes)
            self._status["updated_at"] = datetime.now().astimezone().isoformat()
            try:
                self._atomic_json(self.root / "status.json", self._status)
                self.last_error = ""
            except OSError as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"

    def event(self, stage: str, detail: str, **fields) -> None:
        payload = {"time": datetime.now().astimezone().isoformat(), "stage": stage, "detail": detail, **fields}
        _validate(payload)
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        try:
            with self._lock, (self.root / "events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(line)
                stream.flush()
            self.last_error = ""
        except OSError as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"

    def write_image(self, name: str, frame) -> None:
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
        if not ok:
            raise RuntimeError("failed to encode debug image")
        self.write_jpeg_bytes(name, encoded.tobytes())

    def write_jpeg_bytes(self, name: str, data: bytes) -> None:
        if Path(name).name != name or not name.lower().endswith((".jpg", ".jpeg")):
            raise ValueError("debug image name must be a JPEG file name")
        path = self.root / name
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            with self._lock:
                temporary.write_bytes(data)
                temporary.replace(path)
            self.last_error = ""
        except OSError as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _atomic_json(path: Path, payload: dict) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
