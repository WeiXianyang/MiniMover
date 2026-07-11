from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2


def _merge(target: dict, updates: dict) -> dict:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge(target[key], value)
        else:
            target[key] = value
    return target


class EvidenceStore:
    def __init__(self, root: Path, max_images: int):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_images = max_images

    def save(self, event_id, review_id, capture_type, captured_at, annotated_frame, metadata) -> Path:
        if not event_id.startswith("fire_"):
            raise ValueError("managed event_id must start with fire_")
        ok, encoded = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            raise RuntimeError("failed to encode evidence JPEG")
        name = f"{event_id}_{review_id:03d}_{capture_type}_{captured_at.strftime('%H%M%S%f')}.jpg"
        image_path = self.root / name
        self._atomic_bytes(image_path, encoded.tobytes())
        payload = {
            "event_id": event_id,
            "review_id": review_id,
            "capture_type": capture_type,
            "captured_at": captured_at.isoformat(),
        }
        _merge(payload, dict(metadata))
        self._atomic_json(image_path.with_suffix(".json"), payload)
        self._rotate()
        return image_path

    def update_metadata(self, image_path: Path, updates: dict) -> bool:
        image_path = Path(image_path)
        json_path = image_path.with_suffix(".json")
        if not image_path.is_file() or not json_path.is_file():
            return False
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        _merge(payload, updates)
        self._atomic_json(json_path, payload)
        return True

    def _atomic_bytes(self, path: Path, data: bytes) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(data)
        temporary.replace(path)

    def _atomic_json(self, path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    def _sort_key(self, image_path: Path):
        try:
            payload = json.loads(image_path.with_suffix(".json").read_text(encoding="utf-8"))
            return (datetime.fromisoformat(payload["captured_at"]).timestamp(), image_path.name)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return (float("-inf"), image_path.name)

    def _rotate(self) -> None:
        managed = [path for path in self.root.glob("fire_*.jpg") if path.with_suffix(".json").is_file()]
        for image_path in sorted(managed, key=self._sort_key)[:max(0, len(managed) - self.max_images)]:
            image_path.unlink(missing_ok=True)
            image_path.with_suffix(".json").unlink(missing_ok=True)
