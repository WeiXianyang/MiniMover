#!/usr/bin/env python3
"""Build compact offline demos from real, continuous video footage."""

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
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".m4v", ".webm", ".ogv"}
PLATE_CASCADE_PATH = ASSET_DIR / "hyperlpr_plate_cascade.xml"
_PLATE_CASCADE = None


@dataclass(frozen=True)
class DemoModule:
    key: str
    source: str
    output: str
    title: str
    subtitle: str
    accent: tuple[int, int, int]
    start_seconds: float = 0.0
    annotator: str = "none"


MODULES = (
    DemoModule(
        "license_plate",
        "license_plate_source.webm",
        "license_plate_demo.mp4",
        "LICENSE PLATE RECOGNITION",
        "REAL CONTINUOUS VIDEO - PLATE TARGET",
        (255, 170, 30),
        annotator="plate",
    ),
    DemoModule(
        "traffic_light",
        "traffic_light_source.webm",
        "traffic_light_demo.mp4",
        "TRAFFIC LIGHT RECOGNITION",
        "RED LIGHT DETECTED - REAL VIDEO",
        (20, 40, 245),
        annotator="traffic",
    ),
    DemoModule(
        "fire_smoke",
        "fire_smoke_source.mp4",
        "fire_smoke_demo.mp4",
        "FIRE AND SMOKE RECOGNITION",
        "MODEL RESULT VIDEO - FIRE DETECTED",
        (20, 120, 255),
        start_seconds=3.0,
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
        raise ValueError("Source frame is empty")
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
    _put_centered(frame, subtitle, 342, 0.58, accent)
    return frame


def _writer(path: Path, size: tuple[int, int], fps: int) -> cv2.VideoWriter:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    if not writer.isOpened():
        raise RuntimeError(f"Cannot create MP4 video: {path}")
    return writer


def _open_video(path: Path) -> cv2.VideoCapture:
    if path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError(f"Demo source must be a video, not an image: {path}")
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise FileNotFoundError(f"Demo source video cannot be opened: {path}")
    return capture


def read_source_frames(
    source: Path,
    seconds: int = SECONDS,
    fps: int = FPS,
    start_seconds: float = 0.0,
):
    """Yield sampled real frames, looping short source clips without synthesizing motion."""
    capture = _open_video(source)
    try:
        source_fps = capture.get(cv2.CAP_PROP_FPS) or fps
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count < 2:
            raise ValueError(f"Source video has fewer than two frames: {source}")
        start_frame = int(start_seconds * source_fps) % frame_count
        capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        current_index = start_frame - 1
        current_frame = None

        for output_index in range(seconds * fps):
            target_index = int(start_frame + output_index * source_fps / fps) % frame_count
            if target_index < current_index:
                capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                current_index = -1
                current_frame = None
            while current_index < target_index:
                ok, current_frame = capture.read()
                if not ok:
                    raise RuntimeError(f"Cannot decode source video frame: {source}")
                current_index += 1
            if current_frame is None:
                ok, current_frame = capture.read()
                if not ok:
                    raise RuntimeError(f"Cannot decode source video frame: {source}")
                current_index += 1
            yield current_frame
    finally:
        capture.release()


def video_motion_score(path: Path, sample_frames: int = 24) -> float:
    """Return temporal variation across evenly sampled real video frames."""
    capture = _open_video(path)
    differences: list[float] = []
    previous = None
    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count < 2:
            return 0.0
        wanted = {
            int(index * (frame_count - 1) / max(1, min(sample_frames, frame_count) - 1))
            for index in range(min(sample_frames, frame_count))
        }
        for frame_index in range(frame_count):
            ok, frame = capture.read()
            if not ok:
                break
            if frame_index not in wanted:
                continue
            gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (160, 90))
            if previous is not None:
                differences.append(float(np.mean(cv2.absdiff(previous, gray))))
            previous = gray
    finally:
        capture.release()
    return float(np.mean(differences)) if differences else 0.0



def _plate_cascade() -> cv2.CascadeClassifier:
    global _PLATE_CASCADE
    if _PLATE_CASCADE is None:
        cascade = cv2.CascadeClassifier(str(PLATE_CASCADE_PATH))
        if cascade.empty():
            raise FileNotFoundError(f"HyperLPR plate cascade cannot be loaded: {PLATE_CASCADE_PATH}")
        _PLATE_CASCADE = cascade
    return _PLATE_CASCADE


def _plate_box(frame: np.ndarray):
    best = None
    candidates = _plate_cascade().detectMultiScale(
        frame,
        scaleFactor=1.1,
        minNeighbors=3,
        minSize=(36, 9),
        maxSize=(600, 180),
    )
    for x, y, width, height in candidates:
        roi = frame[y : y + height, x : x + width]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        blue_ratio = float(
            np.mean(
                (hsv[:, :, 0] >= 95)
                & (hsv[:, :, 0] <= 135)
                & (hsv[:, :, 1] >= 70)
            )
        )
        if blue_ratio < 0.1:
            continue
        score = width * height * blue_ratio
        if best is None or score > best[0]:
            best = (score, x, y, width, height, "CHINA PLATE", (255, 170, 30))
    return best


def _traffic_light_box(frame: np.ndarray):
    small = cv2.resize(frame, (max(1, frame.shape[1] // 2), max(1, frame.shape[0] // 2)))
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    red = cv2.bitwise_or(
        cv2.inRange(hsv, (0, 120, 90), (12, 255, 255)),
        cv2.inRange(hsv, (168, 120, 90), (180, 255, 255)),
    )
    masks = (
        ("RED LIGHT", red, (20, 40, 245)),
        ("GREEN LIGHT", cv2.inRange(hsv, (38, 70, 70), (95, 255, 255)), (20, 220, 60)),
        ("YELLOW LIGHT", cv2.inRange(hsv, (15, 100, 100), (38, 255, 255)), (20, 220, 255)),
    )
    best = None
    image_area = small.shape[0] * small.shape[1]
    for label, mask, color in masks:
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        for contour in cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]:
            x, y, width, height = cv2.boundingRect(contour)
            area = width * height
            aspect = width / max(height, 1)
            fill = cv2.countNonZero(mask[y : y + height, x : x + width]) / max(area, 1)
            if 0.45 <= aspect <= 1.8 and 20 <= area <= image_area * 0.02 and fill > 0.35:
                score = area * fill
                if best is None or score > best[0]:
                    best = (score, x * 2, y * 2, width * 2, height * 2, label, color)
    return best


def annotate_target(frame: np.ndarray, annotator: str) -> tuple[np.ndarray, bool]:
    result = frame.copy()
    candidate = _plate_box(result) if annotator == "plate" else _traffic_light_box(result) if annotator == "traffic" else None
    if candidate is None:
        return result, False
    _, x, y, width, height, label, color = candidate
    thickness = max(2, round(min(result.shape[:2]) / 240))
    cv2.rectangle(result, (x, y), (x + width, y + height), color, thickness)
    text_y = max(24, y - 8)
    cv2.putText(result, label, (x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, thickness, cv2.LINE_AA)
    return result, True


def count_annotated_frames(source: Path, annotator: str, stride: int = 6) -> int:
    capture = _open_video(source)
    count = 0
    index = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if index % stride == 0 and annotate_target(frame, annotator)[1]:
                count += 1
            index += 1
    finally:
        capture.release()
    return count

def write_clip(
    source: Path,
    output: Path,
    title: str,
    subtitle: str,
    accent: tuple[int, int, int] = (0, 200, 255),
    seconds: int = SECONDS,
    fps: int = FPS,
    start_seconds: float = 0.0,
    annotator: str = "none",
) -> None:
    writer = _writer(output, FRAME_SIZE, fps)
    try:
        for source_frame in read_source_frames(source, seconds, fps, start_seconds):
            annotated, _ = annotate_target(source_frame, annotator)
            writer.write(fit_frame(annotated, title, subtitle, accent))
    finally:
        writer.release()


def write_combined(videos: list[Path], output: Path, seconds: int = SECONDS, fps: int = FPS) -> None:
    if len(videos) != 3:
        raise ValueError("Combined demo requires exactly three videos")
    captures = [_open_video(path) for path in videos]
    size = (960, 360)
    writer_path = output
    if not str(output).isascii():
        writer_path = output.with_name("combined_demo_build.mp4")
    writer = _writer(writer_path, size, fps)
    try:
        for _ in range(seconds * fps):
            canvas = np.full((size[1], size[0], 3), 14, dtype=np.uint8)
            for column, capture in enumerate(captures):
                ok, frame = capture.read()
                if not ok:
                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frame = capture.read()
                if not ok:
                    raise RuntimeError(f"Cannot decode combined demo source: {videos[column]}")
                panel = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
                canvas[82:262, column * 320 : (column + 1) * 320] = panel
            _put_centered(canvas, "MINIMOVER - THREE VISION MODULES", 48, 0.9, (245, 245, 245))
            _put_centered(canvas, "LICENSE PLATE        TRAFFIC LIGHT        FIRE / SMOKE", 318, 0.62, (0, 210, 255))
            writer.write(canvas)
    finally:
        writer.release()
        for capture in captures:
            capture.release()
    if writer_path != output:
        writer_path.replace(output)


def build_all() -> list[Path]:
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for item in MODULES:
        source = ASSET_DIR / item.source
        if video_motion_score(source) < 1.0:
            raise ValueError(f"Source is not meaningful continuous footage: {source}")
        output = VIDEO_DIR / item.output
        write_clip(
            source,
            output,
            item.title,
            item.subtitle,
            item.accent,
            start_seconds=item.start_seconds,
            annotator=item.annotator,
        )
        outputs.append(output)
    combined = VIDEO_DIR / "\u4e09\u9879\u8bc6\u522b\u7b54\u8fa9\u6f14\u793a.mp4"
    write_combined(outputs, combined)
    outputs.append(combined)
    return outputs


def main() -> int:
    for output in build_all():
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
