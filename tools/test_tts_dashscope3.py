"""List DashScope audio formats and probe WAV synthesis."""

import os
from pathlib import Path
import traceback


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

    print("AudioFormat members:")
    for name in dir(AudioFormat):
        if not name.startswith("_"):
            print(f"  {name}: {getattr(AudioFormat, name)}")

    try:
        synthesizer = SpeechSynthesizer(
            model="cosyvoice-v3-flash",
            voice="longanhuan",
            format=AudioFormat.WAV,
        )
        result = synthesizer.call(text="\u4f60\u597d\u4e16\u754c\u6d4b\u8bd5\u8bed\u97f3")
        print("\nStatus:", result.status_code)
        if hasattr(result, "get_audio_data"):
            audio = result.get_audio_data()
            if audio:
                output = Path("/tmp/test_ds.wav")
                output.write_bytes(audio)
                print("WAV OK:", len(audio), "bytes")
        elif hasattr(result, "output"):
            print("Output:", result.output)
    except Exception:
        traceback.print_exc()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
