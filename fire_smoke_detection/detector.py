#!/usr/bin/env python3
"""Path-stable launcher for the migrated legacy YOLOv5 detector."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
LEGACY = ROOT / "yolov5_runtime" / "detect.py"
MODEL = ROOT / "model" / "best.pt"
OUTPUT = ROOT / "output"


def _normalize_source(value: str) -> str:
    if value.isdigit() or urlparse(value).scheme.lower() in {
        "http",
        "https",
        "rtsp",
        "rtmp",
    }:
        return value
    path = Path(value).expanduser()
    return str((path if path.is_absolute() else Path.cwd() / path).resolve())


def build_command(arguments: Sequence[str]) -> list[str]:
    forwarded = list(arguments)
    if "--source" in forwarded:
        index = forwarded.index("--source") + 1
        if index >= len(forwarded):
            raise ValueError("--source requires a value")
        forwarded[index] = _normalize_source(forwarded[index])
    else:
        forwarded += ["--source", "0"]
    return [
        sys.executable,
        str(LEGACY),
        "--weights",
        str(MODEL),
        "--output",
        str(OUTPUT),
    ] + forwarded


def main(arguments: Sequence[str] | None = None) -> int:
    command = build_command(sys.argv[1:] if arguments is None else arguments)
    return subprocess.run(command, cwd=str(ROOT), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
