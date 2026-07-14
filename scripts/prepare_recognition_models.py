#!/usr/bin/env python3
"""Prepare and verify PC-side recognition models without deploying them to cars."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "recognition_models.json"
LFS_HEADER = b"version https://git-lfs.github.com/spec/v1"


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_model_file(path: Path, expected_size: int, expected_sha256: str) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "path": str(path)}
    with path.open("rb") as stream:
        header = stream.read(len(LFS_HEADER))
    if header == LFS_HEADER:
        return {"status": "lfs_pointer", "path": str(path), "size": path.stat().st_size}
    actual_size = path.stat().st_size
    actual_sha256 = _sha256(path)
    if actual_size != expected_size or actual_sha256.lower() != expected_sha256.lower():
        return {
            "status": "mismatch",
            "path": str(path),
            "size": actual_size,
            "sha256": actual_sha256,
        }
    return {"status": "ok", "path": str(path), "size": actual_size, "sha256": actual_sha256}


def _clone(repository: str, target: Path, revision: str) -> None:
    if target.exists():
        print(f"[SKIP] Runtime already exists: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", repository, str(target)], cwd=ROOT, check=True)
    subprocess.run(["git", "checkout", revision], cwd=target, check=True)


def download_runtimes(manifest: dict[str, Any]) -> None:
    traffic = manifest["models"]["traffic_light_yolo"]
    _clone(
        traffic["runtime_repository"],
        ROOT / traffic["runtime_path"],
        traffic["runtime_revision"],
    )
    plate = manifest["models"]["license_plate_hyperlpr"]
    try:
        _clone(plate["repository"], ROOT / plate["runtime_path"], plate["revision"])
    except subprocess.CalledProcessError:
        target = ROOT / plate["runtime_path"]
        if target.exists():
            raise
        print("[WARN] Gitee clone failed; trying the GitHub mirror.", file=sys.stderr)
        _clone(plate["mirror"], target, plate["revision"])


def check_models(manifest: dict[str, Any]) -> bool:
    all_ok = True
    fire = manifest["models"]["fire_smoke"]
    result = inspect_model_file(ROOT / fire["path"], fire["size"], fire["sha256"])
    print(f"fire_smoke: {result['status']} - {result['path']}")
    if result["status"] != "ok":
        all_ok = False
        print(f"  Run: {fire['download_command']}")

    traffic = manifest["models"]["traffic_light_yolo"]
    result = inspect_model_file(ROOT / traffic["path"], traffic["size"], traffic["sha256"])
    print(f"traffic_light_yolo: {result['status']} - {result['path']}")
    if result["status"] != "ok":
        all_ok = False
        print(f"  Download best_model_12.pt from: {traffic['download_url']}")

    plate = manifest["models"]["license_plate_hyperlpr"]
    plate_root = ROOT / plate["runtime_path"]
    plate_ok = True
    for relative, metadata in plate["files"].items():
        result = inspect_model_file(plate_root / relative, metadata["size"], metadata["sha256"])
        if result["status"] != "ok":
            plate_ok = False
            print(f"license_plate_hyperlpr: {result['status']} - {result['path']}")
    if plate_ok:
        print(f"license_plate_hyperlpr: ok - {plate_root / 'model'}")
    else:
        all_ok = False
        print("  Run this script with --download-runtimes to obtain HyperLPR.")
    return all_ok


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--download-runtimes", action="store_true")
    args = parser.parse_args(arguments)
    manifest = load_manifest(args.manifest)
    if args.download_runtimes:
        download_runtimes(manifest)
    return 0 if check_models(manifest) else 1


if __name__ == "__main__":
    raise SystemExit(main())
