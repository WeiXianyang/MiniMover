#!/usr/bin/env python3
"""Run the external YOLO traffic-light model against a PC or car video source."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from video_source import resolve_source

RUNTIME = ROOT / "Traffic-Light-Detection-Using-YOLOv3"
DETECTOR = RUNTIME / "detect.py"
MODEL = RUNTIME / "weights" / "best_model_12.pt"
CFG = RUNTIME / "cfg" / "yolov3-spp-6cls.cfg"
NAMES = RUNTIME / "data" / "traffic_light.names"
OUTPUT = ROOT / "output_yolo"


def build_command(source: str, forwarded: Sequence[str]) -> list[str]:
    resolved = resolve_source(source)
    command = [
        sys.executable,
        str(DETECTOR),
        "--cfg", str(CFG),
        "--names", str(NAMES),
        "--weights", str(MODEL),
        "--source", resolved,
        "--output", str(OUTPUT),
        "--img-size", "608",
    ]
    extra = list(forwarded)
    if (
        urlparse(resolved).scheme.lower() in {"http", "https", "rtsp", "rtmp"}
        and "--view-img" not in extra
    ):
        command.append("--view-img")
    return command + extra


def validate_runtime() -> None:
    missing = [path for path in (DETECTOR, MODEL, CFG, NAMES) if not path.is_file()]
    if missing:
        details = "\n".join(f"  - {path}" for path in missing)
        raise RuntimeError(
            "Traffic-light YOLO runtime/model is incomplete:\n"
            f"{details}\n"
            "Run: python scripts/prepare_recognition_models.py --download-runtimes\n"
            "Then download best_model_12.pt using the URL in PC_RECOGNITION_GUIDE.md."
        )


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, add_help=True)
    parser.add_argument("source", nargs="?", default="car_A")
    args, forwarded = parser.parse_known_args(arguments)
    try:
        validate_runtime()
    except RuntimeError as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 2
    OUTPUT.mkdir(parents=True, exist_ok=True)
    command = build_command(args.source, forwarded)
    return subprocess.run(command, cwd=RUNTIME, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
