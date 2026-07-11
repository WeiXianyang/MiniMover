#!/usr/bin/env python3
"""Build compact, offline videos for the three-detector defense demo."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

MODULE_DIR = Path(__file__).resolve().parent
ASSET_DIR = MODULE_DIR / "assets"
VIDEO_DIR = MODULE_DIR / "videos"
FRAME_SIZE = (640, 360)
FPS = 12
SECONDS = 10


@dataclass(frozen=True)
class DemoModule:
    key: str
    source: str
    output: str
    title: str
    subtitle: str
    accent: tuple[int, int, int]


MODULES = (
    DemoModule(
        "license_plate",
        "plate_result.jpg",
        "license_plate_demo.mp4",
        "LICENSE PLATE RECOGNITION",
        "PLATE TARGET LOCATED",
        (255, 170, 30),
    ),
    DemoModule(
        "traffic_light",
        "traffic_light_result.jpg",
        "traffic_light_demo.mp4",
        "TRAFFIC LIGHT RECOGNITION",
        "RED LIGHT DETECTED",
        (20, 40, 245),
    ),
    DemoModule(
        "fire_smoke",
        "fire_smoke_result.jpg",
        "fire_smoke_demo.mp4",
        "FIRE AND SMOKE RECOGNITION",
        "FIRE DETECTED",
        (20, 120, 255),
    ),
)


def _put_centered(frame: np.ndarray, text: str, y: int, scale: float, color) -> None:
    thickness = 2
    size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)[0]
    x = max(8, (frame.shape[1] - size[0]) // 2)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def fit_frame(
    image: np.ndarray,
    title: str,
    subtitle: str,
    accent: tuple[int, int, int] = (0, 200, 255),
) -> np.ndarray:
    if image is None or image.size == 0:
        raise ValueError("Source image is empty")
    width, height = FRAME_SIZE
    frame = np.full((height, width, 3), 18, dtype=np.uint8)
    content_top, content_bottom = 54, 306
    area_w, area_h = width, content_bottom - content_top
    scale = min(area_w / image.shape[1], area_h / image.shape[0])
    resized = cv2.resize(
        image,
        (max(1, round(image.shape[1] * scale)), max(1, round(image.shape[0] * scale))),
        interpolation=cv2.INTER_AREA,
    )
    x = (width - resized.shape[1]) // 2
    y = content_top + (area_h - resized.shape[0]) // 2
    frame[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
    cv2.rectangle(frame, (0, 0), (width - 1, height - 1), accent, 3)
    cv2.rectangle(frame, (0, 0), (width, content_top), (12, 12, 12), -1)
    cv2.rectangle(frame, (0, content_bottom), (width, height), (12, 12, 12), -1)
    _put_centered(frame, title, 36, 0.72, (245, 245, 245))
    _put_centered(frame, subtitle, 342, 0.66, accent)
    return frame


def _animated_frame(base: np.ndarray, index: int, total: int) -> np.ndarray:
    phase = np.sin(index / max(total, 1) * np.pi * 4)
    scale = 1.0 + 0.018 * phase
    h, w = base.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), 0, scale)
    return cv2.warpAffine(base, matrix, (w, h), borderMode=cv2.BORDER_REFLECT)


def _writer(path: Path, size: tuple[int, int], fps: int) -> cv2.VideoWriter:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    if not writer.isOpened():
        raise RuntimeError(f"Cannot create MP4 video: {path}")
    return writer


def write_clip(
    image: np.ndarray,
    output: Path,
    title: str,
    subtitle: str,
    accent: tuple[int, int, int] = (0, 200, 255),
    seconds: int = SECONDS,
    fps: int = FPS,
) -> None:
    base = fit_frame(image, title, subtitle, accent)
    total = seconds * fps
    writer = _writer(output, FRAME_SIZE, fps)
    try:
        for index in range(total):
            writer.write(_animated_frame(base, index, total))
    finally:
        writer.release()


def write_combined(frames: list[np.ndarray], output: Path, seconds: int = SECONDS, fps: int = FPS) -> None:
    if len(frames) != 3:
        raise ValueError("Combined demo requires exactly three frames")
    size = (960, 360)
    total = seconds * fps
    writer = _writer(output, size, fps)
    try:
        for index in range(total):
            canvas = np.full((size[1], size[0], 3), 14, dtype=np.uint8)
            for column, frame in enumerate(frames):
                animated = _animated_frame(frame, index, total)
                panel = cv2.resize(animated, (320, 180), interpolation=cv2.INTER_AREA)
                canvas[82:262, column * 320 : (column + 1) * 320] = panel
            _put_centered(canvas, "MINIMOVER - THREE VISION MODULES", 48, 0.9, (245, 245, 245))
            _put_centered(canvas, "LICENSE PLATE        TRAFFIC LIGHT        FIRE / SMOKE", 318, 0.62, (0, 210, 255))
            writer.write(canvas)
    finally:
        writer.release()


def build_all() -> list[Path]:
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    frames: list[np.ndarray] = []
    outputs: list[Path] = []
    for item in MODULES:
        image_path = ASSET_DIR / item.source
        image = cv2.imread(str(image_path))
        if image is None:
            raise FileNotFoundError(f"Demo source image not found: {image_path}")
        output = VIDEO_DIR / item.output
        write_clip(image, output, item.title, item.subtitle, item.accent)
        frames.append(fit_frame(image, item.title, item.subtitle, item.accent))
        outputs.append(output)
    combined = VIDEO_DIR / "三项识别答辩演示.mp4"
    write_combined(frames, combined)
    outputs.append(combined)
    return outputs


def main() -> int:
    for output in build_all():
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
