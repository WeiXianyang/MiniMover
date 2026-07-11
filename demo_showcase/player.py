#!/usr/bin/env python3
"""Loop a local recognition demo video in an independent OpenCV window."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2

MODULE_DIR = Path(__file__).resolve().parent


def resolve_video(value: str | Path, base_dir: Path = MODULE_DIR) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def validate_video(path: Path) -> dict[str, int]:
    if not path.is_file():
        raise FileNotFoundError(f"Demo video not found: {path}")
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise RuntimeError(f"Demo video cannot be opened: {path}")
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"Demo video contains no readable frames: {path}")
        return {
            "frames": int(capture.get(cv2.CAP_PROP_FRAME_COUNT)),
            "width": int(frame.shape[1]),
            "height": int(frame.shape[0]),
        }
    finally:
        capture.release()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", help="MP4 path, relative to demo_showcase by default")
    parser.add_argument("--title", default="Recognition Demo")
    parser.add_argument("--x", type=int, default=40)
    parser.add_argument("--y", type=int, default=40)
    parser.add_argument("--check", action="store_true", help="validate and exit")
    parser.add_argument("--no-loop", dest="loop", action="store_false")
    parser.set_defaults(loop=True)
    return parser


def play(path: Path, title: str, x: int, y: int, loop: bool = True) -> None:
    validate_video(path)
    capture = cv2.VideoCapture(str(path))
    cv2.namedWindow(title, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(title, 640, 360)
    cv2.moveWindow(title, x, y)
    frame_delay = max(1, round(1000 / (capture.get(cv2.CAP_PROP_FPS) or 12)))
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                if not loop:
                    break
                capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            cv2.imshow(title, frame)
            key = cv2.waitKey(frame_delay) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                break
            if cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        capture.release()
        cv2.destroyWindow(title)
        time.sleep(0.05)


def main() -> int:
    args = build_parser().parse_args()
    path = resolve_video(args.video)
    info = validate_video(path)
    if args.check:
        print(f"OK {path} {info['width']}x{info['height']} frames={info['frames']}")
        return 0
    play(path, args.title, args.x, args.y, args.loop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
