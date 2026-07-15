#!/usr/bin/env python3
"""
轻量化红绿灯视觉识别
基于 HSV 色彩空间 + HoughCircles 圆检测，纯 OpenCV 实现
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from video_source import resolve_source

from traffic_light.debug_telemetry import DebugTelemetry, NullTelemetry


class TrafficLightDetector:
    """红绿灯检测器"""

    def __init__(self, min_color_ratio: float = 0.6, circle_accumulator_threshold: int = 35):
        # ????????????????????????????????
        self.min_color_ratio = min_color_ratio
        self.circle_accumulator_threshold = circle_accumulator_threshold
        # HSV ???????????????
        self.color_ranges = {
            'red':    [(0, 120, 70),   (10, 255, 255)],   # ?????
            'red2':   [(170, 120, 70), (180, 255, 255)],  # ?????(HSV??)
            'yellow': [(20, 100, 100), (35, 255, 255)],
            'green':  [(40, 50, 50),   (90, 255, 255)],
        }

    def detect(self, frame, scale: float = 0.5):
        """
        Detect traffic lights in a frame.
        scale: internal processing scale (lower = faster, default 0.5)
        Returns: (result_frame, state)
          state: 'red' | 'yellow' | 'green' | 'none'
        """
        h0, w0 = frame.shape[:2]
        # Scale down for speed
        if scale < 1.0:
            small = cv2.resize(frame, (int(w0 * scale), int(h0 * scale)))
        else:
            small = frame

        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        h, w = small.shape[:2]

        # ROI: top half of frame (where traffic lights usually are)
        hsv_roi = hsv[0:h//2, :]
        gray_roi = cv2.cvtColor(small[0:h//2, :], cv2.COLOR_BGR2GRAY)

        # Gaussian blur
        blurred = cv2.GaussianBlur(gray_roi, (7, 7), 2)

        # HoughCircles (dp=1.5 for speed)
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.5,
            minDist=30,
            param1=50,
            param2=self.circle_accumulator_threshold,
            minRadius=6,
            maxRadius=50
        )

        detected_state = 'none'
        best = None  # (x, y, r, color)

        if circles is not None:
            circles = np.uint16(np.around(circles))

            for (cx, cy, r) in circles[0]:
                # Mask for the circle interior
                mask = np.zeros(hsv_roi.shape[:2], dtype=np.uint8)
                cv2.circle(mask, (cx, cy), max(r - 2, 1), 255, -1)

                for color_name, ranges in self.color_ranges.items():
                    if color_name == 'red2':
                        continue  # merged with red
                    lower, upper = ranges

                    if color_name == 'red':
                        mask_r1 = cv2.inRange(hsv_roi, self.color_ranges['red'][0],
                                              self.color_ranges['red'][1])
                        mask_r2 = cv2.inRange(hsv_roi, self.color_ranges['red2'][0],
                                              self.color_ranges['red2'][1])
                        color_mask = cv2.bitwise_or(mask_r1, mask_r2)
                    else:
                        color_mask = cv2.inRange(hsv_roi, lower, upper)

                    overlap = cv2.bitwise_and(mask, color_mask)
                    ratio = np.sum(overlap > 0) / (np.sum(mask > 0) + 1)

                    if ratio > self.min_color_ratio:
                        clean_name = 'red' if color_name == 'red' else color_name
                        if best is None or r > best[2]:
                            best = (cx, cy, r, clean_name)
                            detected_state = clean_name

        # Scale coordinates back to original size
        result = frame.copy()
        if best and scale < 1.0:
            cx, cy, r, color = best
            cx = int(cx / scale)
            cy = int(cy / scale)
            r = int(r / scale)
            best_resized = (cx, cy, r, color)
        elif best:
            best_resized = best
        else:
            best_resized = None

        if best_resized:
            cx, cy, r, color = best_resized
            colors = {'red': (0, 0, 255), 'yellow': (0, 255, 255), 'green': (0, 255, 0)}
            cv2.circle(result, (cx, cy), r, colors.get(color, (255, 255, 255)), 2)
            cv2.circle(result, (cx, cy), 2, colors.get(color, (255, 255, 255)), 3)

            text = f"{color.upper()} LIGHT"
            cv2.putText(result, text, (10, h0 - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, colors.get(color, (255, 255, 255)), 2)

        return result, detected_state


def open_capture(source: str) -> cv2.VideoCapture:
    resolved = resolve_source(source)
    return cv2.VideoCapture(int(resolved) if resolved.isdigit() else resolved)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="HSV traffic light detector")
    parser.add_argument("source", nargs="?", default="0",
                        help="0, file/URL, car_A, car_B, proxy:car_A, or proxy:car_B")
    parser.add_argument("--monitor-debug-dir", type=str, default="",
                        help="debug telemetry output directory for the monitor window")
    parser.add_argument("--no-view", action="store_true",
                        help="suppress the OpenCV preview window (useful under a monitor window)")
    parser.add_argument("--min-color-ratio", type=float, default=0.50,
                        help="minimum color ratio for detection (default: 0.50)")
    parser.add_argument("--circle-threshold", type=int, default=25,
                        help="HoughCircles accumulator threshold (default: 25)")
    parser.add_argument("--skip-frames", type=int, default=3,
                        help="run detection every N frames to reduce CPU load (default: 3, 1=every frame)")
    args = parser.parse_args()

    detector = TrafficLightDetector(
        min_color_ratio=args.min_color_ratio,
        circle_accumulator_threshold=args.circle_threshold,
    )
    requested_source = args.source
    source = resolve_source(requested_source)

    telemetry = DebugTelemetry(Path(args.monitor_debug_dir)) if args.monitor_debug_dir else NullTelemetry()
    if telemetry.enabled:
        telemetry.reset()
        telemetry.update(source=source, process={"state": "running"},
                         detector={"type": "HSV+HoughCircles", "state": "running",
                                   "min_color_ratio": args.min_color_ratio,
                                   "circle_threshold": args.circle_threshold})
        telemetry.event("started", f"Traffic light detector started; source: {source}")

    print("=" * 50)
    print("  Traffic Light Detector - 红绿灯识别")
    print(f"  Source: {source}")
    print("  Press 'q' to quit | 's' to save screenshot")
    print("=" * 50)

    cap = open_capture(source)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video source: {source}", file=sys.stderr)
        return 1
    # Limit buffer to reduce latency
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    import time as _time
    last_debug_frame = 0.0
    last_state = "none"
    last_result = None
    frame_count = 0
    skip = max(1, args.skip_frames)
    failure = None
    fps_timer = _time.monotonic()
    fps_counter = 0
    print(f"Detection every {skip} frame(s)  |  0.5x scale  |  buffer=1")
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] Cannot read a frame from the video source.", file=sys.stderr)
                return 1

            frame_count += 1
            fps_counter += 1
            if frame_count % skip == 0:
                result, state = detector.detect(frame)
                # Store reference only — detect() already returns a copy
                last_result = (result, state)
            else:
                # Reuse last detection; overlay text on raw frame for freshness
                if last_result is not None:
                    _, state = last_result
                else:
                    state = "none"
                # Show raw frame with cached state label (faster than copying)
                result = frame
                if state != "none":
                    colors = {'red': (0, 0, 255), 'yellow': (0, 255, 255), 'green': (0, 255, 0)}
                    cv2.putText(result, f"{state.upper()} LIGHT", (10, frame.shape[0] - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, colors.get(state, (255, 255, 255)), 2)

            # FPS counter (every 5s)
            elapsed = _time.monotonic() - fps_timer
            if elapsed >= 5.0:
                fps = fps_counter / elapsed
                print(f"FPS: {fps:.1f}  |  State: {state}")
                if telemetry.enabled:
                    telemetry.event("fps", f"{fps:.1f} fps", fps=round(fps, 1))
                fps_timer = _time.monotonic()
                fps_counter = 0

            now_monotonic = _time.monotonic()
            if telemetry.enabled:
                if state != last_state:
                    last_state = state
                    telemetry.update(detector={"state": state})
                    telemetry.event("state_changed", f"Traffic light: {state}", light_state=state)
                if now_monotonic - last_debug_frame >= 0.5:
                    telemetry.write_image("latest_frame.jpg", result)
                    last_debug_frame = now_monotonic

            if not args.no_view:
                cv2.imshow("Traffic Light Detection", result)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    if telemetry.enabled:
                        telemetry.update(process={"state": "stopped"})
                        telemetry.event("stopped", "User pressed 'q'")
                    return 0
                if key == ord('s'):
                    cv2.imwrite("screenshot.jpg", result)
                    print("Screenshot saved: screenshot.jpg")
            else:
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    if telemetry.enabled:
                        telemetry.update(process={"state": "stopped"})
                        telemetry.event("stopped", "User pressed 'q'")
                    return 0
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
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())
