#!/usr/bin/env python3
"""Path-stable launcher for the migrated legacy YOLOv5 detector."""

from __future__ import annotations

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

LEGACY = ROOT / "yolov5_runtime" / "detect.py"
MODEL = ROOT / "model" / "best.pt"
OUTPUT = ROOT / "output"


def _normalize_source(value: str) -> str:
    source = resolve_source(value)
    if source.isdigit() or urlparse(source).scheme.lower() in {
        "http",
        "https",
        "rtsp",
        "rtmp",
    }:
        return source
    path = Path(source).expanduser()
    return str((path if path.is_absolute() else Path.cwd() / path).resolve())


def build_command(arguments: Sequence[str]) -> list[str]:
    forwarded = list(arguments)
    if "--device" in forwarded:
        index = forwarded.index("--device")
        if index + 1 >= len(forwarded):
            raise ValueError("--device requires a value")
        del forwarded[index:index + 2]
    if "--source" in forwarded:
        index = forwarded.index("--source") + 1
        if index >= len(forwarded):
            raise ValueError("--source requires a value")
        forwarded[index] = _normalize_source(forwarded[index])
    else:
        forwarded += ["--source", "0"]
    if "--no-view" not in forwarded and "--view-img" not in forwarded:
        source_value = forwarded[forwarded.index("--source") + 1]
        if urlparse(source_value).scheme.lower() in {"http", "https", "rtsp", "rtmp"}:
            forwarded.append("--view-img")

    return [
        sys.executable,
        str(LEGACY),
        "--weights",
        str(MODEL),
        "--output",
        str(OUTPUT),
        "--device",
        "0",
    ] + forwarded


def main(arguments: Sequence[str] | None = None) -> int:
    command = build_command(sys.argv[1:] if arguments is None else arguments)
    return subprocess.run(command, cwd=str(ROOT), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
