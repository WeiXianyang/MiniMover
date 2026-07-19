"""Start the PC ASR server with local voice environment variables loaded."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
PORT = 8766


def load_env(paths: list[Path]) -> dict[str, str]:
    env = os.environ.copy()
    for path in paths:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env.setdefault(key.strip(), value.strip())
    return env


def stop_listener(port: int) -> None:
    result = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or "LISTENING" not in line or f":{port}" not in line:
            continue
        pid = parts[-1]
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, check=False)
        print(f"Killed PID {pid}")


def main() -> int:
    env = load_env([ROOT / ".env.voice", ROOT / ".tts.env"])
    stop_listener(PORT)
    time.sleep(1)

    log_path = ROOT / "asr_debug.log"
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n=== ASR START {time.time()} ===\n")
        log.flush()
        process = subprocess.Popen(
            [sys.executable, "-u", "voice_assistant/pc_asr_server.py", str(PORT)],
            cwd=ROOT,
            stderr=log,
            stdout=log,
            env=env,
        )
        print(f"ASR PID {process.pid} started, logging to {log_path}")
        time.sleep(3600)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
