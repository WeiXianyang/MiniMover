#!/usr/bin/env python3
"""Open a MiniMover-compatible video source for real-time license plate recognition."""

from __future__ import annotations

import argparse
import os
import sys
import types
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parent
HYPERLPR_ROOT = ROOT / "lp-HyperLPR"
for path in (REPOSITORY_ROOT, HYPERLPR_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from video_source import resolve_source

from traffic_light.debug_telemetry import DebugTelemetry, NullTelemetry

_OPENCV_FIND_CONTOURS_ORIGINAL = None


def parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HyperLPR real-time license plate recognition")
    parser.add_argument(
        "source",
        nargs="?",
        default="0",
        help="0, file/URL, car_A, car_B, proxy:car_A, or proxy:car_B",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.7,
        help="minimum HyperLPR confidence to display (default: 0.7)",
    )
    parser.add_argument(
        "--monitor-debug-dir",
        type=str,
        default="",
        help="debug telemetry output directory for the monitor window",
    )
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="suppress the OpenCV preview window (useful under a monitor window)",
    )
    parser.add_argument(
        "--skip-frames",
        type=int,
        default=5,
        help="run detection every N frames to reduce CPU load (default: 5, 1=every frame)",
    )
    parser.add_argument(
        "--detect-width",
        type=int,
        default=640,
        help="resize frame width before detection to reduce CPU load (default: 640)",
    )
    return parser.parse_args(arguments)


@contextmanager
def hyperlpr_working_directory() -> Iterator[None]:
    """Keep legacy HyperLPR relative model/font paths valid without changing global startup."""
    previous = Path.cwd()
    os.chdir(HYPERLPR_ROOT)
    try:
        yield
    finally:
        os.chdir(previous)


def install_numpy_compatibility() -> None:
    """Restore the NumPy aliases referenced by the bundled legacy HyperLPR code."""
    if getattr(np, "float", None) is None:
        np.float = float
    if getattr(np, "int", None) is None:
        np.int = int


def install_opencv_compatibility() -> None:
    """Normalize OpenCV 4 findContours output for legacy HyperLPR modules."""
    global _OPENCV_FIND_CONTOURS_ORIGINAL
    if _OPENCV_FIND_CONTOURS_ORIGINAL is not None:
        return
    _OPENCV_FIND_CONTOURS_ORIGINAL = cv2.findContours

    def legacy_find_contours(image, mode, method, *args, **kwargs):
        result = _OPENCV_FIND_CONTOURS_ORIGINAL(image, mode, method, *args, **kwargs)
        if len(result) == 2:
            contours, hierarchy = result
            return image, contours, hierarchy
        return result

    cv2.findContours = legacy_find_contours


def install_keras_compatibility() -> None:
    """Bridge Keras 3 module renames used by the bundled legacy HyperLPR code."""
    try:
        from keras.layers import PReLU
        from keras import optimizers
    except ImportError as error:
        raise RuntimeError(
            "HyperLPR requires Keras/TensorFlow. Install the dependencies in "
            "traffic_light/lp-HyperLPR/requirements.txt."
        ) from error

    module_name = "keras.layers.advanced_activations"
    compatibility_module = sys.modules.get(module_name)
    if compatibility_module is None:
        compatibility_module = types.ModuleType(module_name)
        sys.modules[module_name] = compatibility_module
    compatibility_module.PReLU = PReLU
    if not hasattr(optimizers, "adam"):
        optimizers.adam = optimizers.Adam


def require_tensorflow_gpu() -> bool:
    """Check if TensorFlow has a CUDA GPU; return True if available.
    On Windows TensorFlow >= 2.11 does not support native GPU — we fall back to CPU.
    """
    try:
        import tensorflow as tf
    except ImportError as error:
        raise RuntimeError("HyperLPR requires TensorFlow") from error
    gpu_devices = tf.config.list_physical_devices("GPU")
    if not gpu_devices:
        print("WARNING: No TensorFlow CUDA GPU found — running on CPU (slower)", file=sys.stderr)
        return False
    return True


def load_recognizer():
    """Load the bundled Python 3 HyperLPR pipeline only when the plate detector starts."""
    install_numpy_compatibility()
    install_opencv_compatibility()
    install_keras_compatibility()
    require_tensorflow_gpu()
    with hyperlpr_working_directory():
        from hyperlpr_py3 import pipline
    return pipline


def open_capture(source: str) -> cv2.VideoCapture:
    resolved = resolve_source(source)
    return cv2.VideoCapture(int(resolved) if resolved.isdigit() else resolved)


def show_loading_preview(frame: np.ndarray) -> None:
    """Show the live feed immediately while the legacy model is loading."""
    preview = frame.copy()
    cv2.putText(preview, "Loading license plate model...", (10, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2, cv2.LINE_AA)
    cv2.imshow("License Plate Detection", preview)
    cv2.waitKey(1)


def main(arguments: list[str] | None = None) -> int:
    args = parse_args(arguments)
    source = resolve_source(args.source)
    capture = open_capture(source)
    if not capture.isOpened():
        print(f"[ERROR] Cannot open video source: {source}", file=sys.stderr)
        return 1

    success, first_frame = capture.read()
    if not success:
        capture.release()
        print("[ERROR] Cannot read a frame from the video source.", file=sys.stderr)
        return 1

    show_loading_preview(first_frame)
    try:
        pipeline = load_recognizer()
    except (ImportError, RuntimeError, OSError) as error:
        capture.release()
        cv2.destroyAllWindows()
        print(f"[ERROR] Cannot initialize HyperLPR: {error}", file=sys.stderr)
        return 1

    telemetry = DebugTelemetry(Path(args.monitor_debug_dir)) if args.monitor_debug_dir else NullTelemetry()
    if telemetry.enabled:
        telemetry.reset()
        telemetry.update(source=source, process={"state": "running"},
                         detector={"type": "HyperLPR", "state": "running", "hit_count": 0})
        telemetry.event("started", f"Plate detector started; source: {source}")

    print("=" * 50)
    print("  License Plate Detector - 车牌号识别")
    print(f"  Source: {source}")
    print("  Press 'q' to quit | 's' to save screenshot")
    print("=" * 50)

    import time as _time
    last_debug_frame = 0.0
    last_detection_text = ""
    total_hits = 0
    latest_plates = ""
    frame_count = 0
    failure = None
    skip = max(1, args.skip_frames)
    detect_width = max(320, args.detect_width)
    print(f"Detection every {skip} frame(s), resize to width={detect_width}")
    try:
        frame = first_frame
        while True:
            if not success:
                print("[ERROR] Cannot read a frame from the video source.", file=sys.stderr)
                return 1

            frame_count += 1
            if frame_count % skip == 0:
                # Detection frame: resize and run HyperLPR
                h, w = frame.shape[:2]
                scale = detect_width / w
                if scale < 0.95:
                    small = cv2.resize(frame, (detect_width, int(h * scale)))
                else:
                    small = frame
                with hyperlpr_working_directory():
                    result, candidates = pipeline.SimpleRecognizePlateByE2E(small.copy())
                accepted = [candidate for candidate in candidates if candidate[2] >= args.confidence]
                if accepted:
                    last_detection_text = " | ".join(f"{plate} ({confidence:.2f})" for _, plate, confidence in accepted)
                    if telemetry.enabled:
                        total_hits += 1
                        if last_detection_text != latest_plates:
                            latest_plates = last_detection_text
                            telemetry.update(detector={"hit_count": total_hits, "latest_plates": latest_plates})
                            telemetry.event("plate_detected", latest_plates, count=len(accepted))
            else:
                # Skip frame: just show the original frame with cached result
                result = frame.copy()

            if last_detection_text:
                cv2.putText(result, last_detection_text, (10, result.shape[0] - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)

            now_monotonic = _time.monotonic()
            if telemetry.enabled and now_monotonic - last_debug_frame >= 0.2:
                telemetry.write_image("latest_frame.jpg", result)
                telemetry.update(detector={"hit_count": total_hits})
                last_debug_frame = now_monotonic

            if not args.no_view:
                cv2.imshow("License Plate Detection", result)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    if telemetry.enabled:
                        telemetry.update(process={"state": "stopped"})
                        telemetry.event("stopped", "User pressed 'q'")
                    return 0
                if key == ord("s"):
                    cv2.imwrite("plate_screenshot.jpg", result)
                    print("Screenshot saved: plate_screenshot.jpg")
            else:
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    if telemetry.enabled:
                        telemetry.update(process={"state": "stopped"})
                        telemetry.event("stopped", "User pressed 'q'")
                    return 0

            success, frame = capture.read()
            if not success:
                print("[ERROR] Cannot read a frame from the video source.", file=sys.stderr)
                return 1
    except Exception as exc:
        failure = f"{type(exc).__name__}: {exc}"
        if telemetry.enabled:
            telemetry.update(process={"state": "failed", "error": failure})
            telemetry.event("detector_failed", failure)
        print(f"[ERROR] {failure}", file=sys.stderr)
        return 1
    finally:
        if telemetry.enabled and failure is None:
            telemetry.update(process={"state": "stopped"})
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())
