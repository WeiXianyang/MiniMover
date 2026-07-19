"""Inspect and probe the DashScope TTS call interface."""

import inspect
import os


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

    print("Signature:", inspect.signature(SpeechSynthesizer.call))
    try:
        result = SpeechSynthesizer.call(
            model="cosyvoice-v3-flash",
            text="\u4f60\u597d\u4e16\u754c",
            voice="longanhuan",
            format="wav",
        )
        print("Status:", result.status_code)
        print("Output:", result.output)
    except Exception as exc:
        print("Error:", exc)

    try:
        result = SpeechSynthesizer.call(text="\u4f60\u597d\u4e16\u754c2", voice="longanhuan", format="wav")
        print("Status2:", result.status_code)
    except Exception as exc:
        print("Error2:", exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
