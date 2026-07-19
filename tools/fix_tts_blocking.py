#!/usr/bin/env python3
"""Make the Jetson audio player block until ``aplay`` finishes."""

from __future__ import annotations

from pathlib import Path
import re

TARGET = Path("/home/jetson/MiniMover/audio/icar_audio.py")

OLD = """    def play(self, wav_data: bytes) -> None:
        self.stop()
        # aplay ALSA \u76f4\u63a5\u8f93\u51fa, systemd \u8fdb\u7a0b\u4e5f\u80fd\u7528\uff08\u65e0\u9700 PulseAudio\uff09
        tmp = tempfile.NamedTemporaryFile(suffix=\".wav\", delete=False)
        tmp.write(wav_data)
        tmp.close()
        with self._lock:
            self._proc = subprocess.Popen(
                [\"aplay\", \"-D\", \"plughw:0,0\", \"-q\", tmp.name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._status = \"playing\"
        def _cleanup():
            self._proc.wait()
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
        threading.Thread(target=_cleanup, daemon=True).start()"""

NEW = """    def play(self, wav_data: bytes) -> None:
        self.stop()
        # aplay ALSA \u76f4\u63a5\u8f93\u51fa \u2014 \u963b\u585e\u76f4\u5230\u64ad\u5b8c\uff0c\u9632\u6b62 TTS \u56de\u58f0
        tmp = tempfile.NamedTemporaryFile(suffix=\".wav\", delete=False)
        tmp.write(wav_data)
        tmp.close()
        with self._lock:
            self._proc = subprocess.Popen(
                [\"aplay\", \"-D\", \"plughw:0,0\", \"-q\", tmp.name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self._status = \"playing\"
        self._proc.wait()  # \u963b\u585e\u7b49\u5f85\u64ad\u5b8c \u2014\u2014 \u5173\u952e\uff01
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        with self._lock:
            self._status = \"idle\""""


def main() -> int:
    content = TARGET.read_text(encoding="utf-8")
    if OLD not in content:
        print("ERROR: old pattern not found!")
        match = re.search(r"def play\(self, wav_data", content)
        if match:
            print(content[match.start() : match.start() + 500])
        return 1

    TARGET.write_text(content.replace(OLD, NEW), encoding="utf-8")
    print("OK: play() now blocks until aplay finishes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
