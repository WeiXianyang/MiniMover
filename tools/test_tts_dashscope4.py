"""Probe supported DashScope TTS audio formats."""

import os
from pathlib import Path


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

    formats = [
        AudioFormat.WAV_16000HZ_MONO_16BIT,
        AudioFormat.WAV_24000HZ_MONO_16BIT,
        AudioFormat.PCM_16000HZ_MONO_16BIT,
    ]
    for audio_format in formats:
        try:
            synthesizer = SpeechSynthesizer(
                model="cosyvoice-v3-flash",
                voice="longanhuan",
                format=audio_format,
            )
            result = synthesizer.call(text="\u4f60\u597d\u4e16\u754c\uff0c\u8fd9\u662f\u767e\u70bc\u8bed\u97f3\u5408\u6210\u6d4b\u8bd5")
            print(f"Format {audio_format.name}: status={result.status_code}")
            audio = result.get_audio_data()
            if audio:
                output = Path(f"/tmp/tts_{audio_format.name}.wav")
                output.write_bytes(audio)
                print(f"WAV: {len(audio)} bytes -> {output}")
            else:
                print(f"No audio, output={result.output}")
        except Exception as exc:
            print(f"{audio_format.name} error: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
