#!/usr/bin/env python3
"""Download the pinned ShortMedKG JSONL snapshot for the hospital-guide demo."""

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib import request


SHORTMEDKG_COMMIT = "7fbf8e50144c9b4627ddf33410de8c7d3ab5240e"
SHORTMEDKG_SOURCE_URL = (
    "https://raw.githubusercontent.com/wingter562/ShortMedKG/"
    + SHORTMEDKG_COMMIT
    + "/input_v4.jsonl"
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "voice_assistant" / "data" / "shortmedkg" / "input_v4.jsonl"


def verify_sha256(path, expected_digest):
    """Return whether *path* matches the expected hexadecimal SHA-256 digest."""
    expected = str(expected_digest or "").strip().lower()
    if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
        return False
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return False
    return digest.hexdigest() == expected


def _validate_jsonl(path):
    records = 0
    with Path(path).open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError("downloaded file is not valid JSONL at line %d" % line_number) from exc
            if not isinstance(value, dict):
                raise ValueError("downloaded JSONL record %d is not an object" % line_number)
            records += 1
    if not records:
        raise ValueError("downloaded JSONL file is empty")
    return records


def _atomic_write_bytes(path, content):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=target.parent, prefix=target.name + ".", suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def download_shortmedkg(output=DEFAULT_OUTPUT, timeout=30.0):
    """Download, validate, checksum, and atomically install the pinned snapshot."""
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=target.parent, prefix=target.name + ".", suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            with request.urlopen(SHORTMEDKG_SOURCE_URL, timeout=float(timeout)) as response:
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())

        records = _validate_jsonl(temporary)
        digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        os.replace(temporary, target)
        temporary = None

        metadata = {
            "source_url": SHORTMEDKG_SOURCE_URL,
            "commit": SHORTMEDKG_COMMIT,
            "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "bytes": target.stat().st_size,
            "sha256": digest,
            "records": records,
        }
        _atomic_write_bytes(
            target.with_name(target.name + ".metadata.json"),
            (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )
        return metadata
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Download the pinned ShortMedKG JSONL snapshot for MiniMover."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    metadata = download_shortmedkg(args.output, args.timeout)
    print(
        "Downloaded %d records (%d bytes), SHA-256: %s"
        % (metadata["records"], metadata["bytes"], metadata["sha256"])
    )


if __name__ == "__main__":
    main()
