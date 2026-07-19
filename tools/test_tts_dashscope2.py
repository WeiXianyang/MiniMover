"""Inspect the DashScope SpeechSynthesizer constructor."""

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

    print("__init__:", inspect.signature(SpeechSynthesizer.__init__))
    try:
        print("Source:", inspect.getsource(SpeechSynthesizer.__init__)[:800])
    except (OSError, TypeError):
        pass

    try:
        synthesizer = SpeechSynthesizer(model="cosyvoice-v3-flash", voice="longanhuan", format="wav")
        result = synthesizer.call(text="\u4f60\u597d\u4e16\u754c")
        print("Status:", result.status_code)
        print("Output:", result.output)
    except Exception as exc:
        print("Error1:", exc)

    print("\nClass dir:", [name for name in dir(SpeechSynthesizer) if not name.startswith("__")])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
