"""Synthesize and play a DashScope WAV sample."""

import os
from pathlib import Path
import subprocess


def configure_credentials() -> None:
    api_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("MINIMOVER_DASHSCOPE_API_KEY")
    workspace = os.environ.get("DASHSCOPE_WORKSPACE_ID") or os.environ.get("MINIMOVER_DASHSCOPE_WORKSPACE_ID")
    if not api_key:
        raise RuntimeError("Set DASHSCOPE_API_KEY or MINIMOVER_DASHSCOPE_API_KEY")
    os.environ["DASHSCOPE_API_KEY"] = api_key
    if workspace:
        os.environ["DASHSCOPE_WORKSPACE_ID"] = workspace


def main() -> int:
    configure_credentials()
    from dashscope.audio.tts_v2 import SpeechSynthesizer
    from dashscope.audio.tts_v2.speech_synthesizer import AudioFormat

    synthesizer = SpeechSynthesizer(
        model="cosyvoice-v3-flash",
        voice="longanhuan",
        format=AudioFormat.WAV_16000HZ_MONO_16BIT,
    )
    audio = synthesizer.call(text="\u4f60\u597d\u4e16\u754c\uff0c\u8fd9\u662f\u767e\u70bc\u8bed\u97f3\u5408\u6210\u6d4b\u8bd5")
    output = Path("/tmp/tts_ok.wav")
    output.write_bytes(audio)
    print(f"Saved {len(audio)} bytes to {output}")
    subprocess.run(["paplay", str(output)], check=False)
    print("Played!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
