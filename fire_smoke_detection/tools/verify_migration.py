#!/usr/bin/env python3
"""Verify migrated trees and write SHA-256 evidence."""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

IGNORED_DIRS = {"__pycache__", ".pytest_cache"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


@dataclass(frozen=True)
class TreeSummary:
    file_count: int
    byte_count: int


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in relative.parts):
            continue
        if path.suffix.lower() in IGNORED_SUFFIXES:
            continue
        yield path


def tree_summary(root: Path) -> TreeSummary:
    files = list(iter_files(root))
    return TreeSummary(len(files), sum(path.stat().st_size for path in files))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compare_trees(source: Path, target: Path) -> list[str]:
    source_files = {path.relative_to(source): path for path in iter_files(source)}
    target_files = {path.relative_to(target): path for path in iter_files(target)}
    problems: list[str] = []
    for relative in sorted(source_files.keys() | target_files.keys()):
        if relative not in source_files:
            problems.append(f"extra target file: {relative}")
        elif relative not in target_files:
            problems.append(f"missing target file: {relative}")
        elif source_files[relative].stat().st_size != target_files[relative].stat().st_size:
            problems.append(f"size mismatch: {relative}")
        elif sha256(source_files[relative]) != sha256(target_files[relative]):
            problems.append(f"hash mismatch: {relative}")
    return problems


def write_checksums(root: Path, files: Iterable[Path], manifest: Path) -> None:
    lines = [f"{sha256(path)}  {path.relative_to(root).as_posix()}" for path in files]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--target-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    mappings = [
        (args.source_root / "VOC2020", args.target_root / "training" / "VOC2020"),
        (args.source_root / "yolov5" / "runs", args.target_root / "training" / "runs"),
        (args.source_root / "yolov5" / "scripts", args.target_root / "training" / "scripts"),
        (args.source_root / "result", args.target_root / "evidence" / "results" / "result"),
        (args.source_root / "xml_lab", args.target_root / "evidence" / "results" / "xml_lab"),
    ]
    problems: list[str] = []
    for source, target in mappings:
        problems.extend(f"{source.name}: {problem}" for problem in compare_trees(source, target))

    source_model = args.source_root / "yolov5" / "best.pt"
    target_model = args.target_root / "model" / "best.pt"
    if sha256(source_model) != sha256(target_model):
        problems.append("model: hash mismatch")

    critical = [
        target_model,
        args.target_root / "training" / "fire_smoke.yaml",
        args.target_root / "evidence" / "source-history.bundle",
        args.target_root / "evidence" / "working-tree.patch",
        args.target_root / "evidence" / "provenance.txt",
    ]
    write_checksums(args.target_root, critical, args.manifest)

    for problem in problems:
        print(f"FAIL: {problem}")
    if problems:
        return 1
    print("Migration tree verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
