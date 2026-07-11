#!/usr/bin/env bash
set -euo pipefail

MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$MODULE_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[ERROR] $PYTHON_BIN was not found on PATH." >&2
  exit 1
fi

if [[ ! -f "$MODULE_DIR/model/best.pt" ]]; then
  echo "[ERROR] Missing model/best.pt" >&2
  exit 1
fi

if [[ $# -eq 0 ]]; then
  exec "$PYTHON_BIN" detector.py --source 0 --view-img
else
  exec "$PYTHON_BIN" detector.py "$@"
fi
