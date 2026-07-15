#!/usr/bin/env python3
"""Launch 3 monitor windows and keep them alive.
Press Ctrl+C in the terminal to close all windows.
"""
import subprocess, sys, time, signal, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = [
    ROOT / "traffic_light" / "plate_monitor_window.py",
    ROOT / "traffic_light" / "traffic_light_monitor_window.py",
    ROOT / "fire_smoke_detection" / "fire_monitor_test_window.py",
]

procs = []

def cleanup():
    print("\nShutting down monitors...")
    for p in procs:
        if p.poll() is None:
            p.terminate()
    for p in procs:
        try:
            p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            p.kill()
    print("All monitors stopped.")

signal.signal(signal.SIGINT, lambda s, f: cleanup() or sys.exit(0))
signal.signal(signal.SIGTERM, lambda s, f: cleanup() or sys.exit(0))

for s in SCRIPTS:
    if not s.is_file():
        print(f"SKIP: {s} not found")
        continue
    p = subprocess.Popen(
        [sys.executable, str(s)],
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    procs.append(p)
    print(f"[PID {p.pid}] {s.name}")

print(f"\n3 windows should be on your desktop.")
print("Press Ctrl+C to close all windows.\n")

try:
    while True:
        time.sleep(1)
        # Check if any window closed
        for i, p in enumerate(procs):
            if p.poll() is not None:
                print(f"[exited] {SCRIPTS[i].name}")
                procs[i] = None
        # Remove dead processes
        procs[:] = [p for p in procs if p is not None]
        if not procs:
            print("All windows closed. Exiting.")
            break
except KeyboardInterrupt:
    cleanup()
