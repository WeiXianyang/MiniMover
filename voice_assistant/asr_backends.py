"""Configurable DashScope ASR backends for short, VAD-delimited utterances."""

from __future__ import annotations

import base64
import io
import os
import sys
import tempfile
import wave
from typing import Any

import numpy as np

DEFAULT_SAMPLE_RATE = 16000
MIN_UTTERANCE_SECONDS = 0.3


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _qwen3_text(response: Any) -> str:
    status_code = _field(response, "status_code", 200)
    if status_code not in (None, 200):
        raise RuntimeError(f"Qwen3-ASR request failed with status {status_code}")

    output = _field(response, "output", {})
    choices = _field(output, "choices", []) or []
    if not choices:
        return ""
    message = _field(choices[0], "message", {})
    content = _field(message, "content", [])
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, (list, tuple)):
        return ""
    return "".join(
        str(_field(item, "text", "") or "") for item in content
    ).strip()


def recognize_qwen3(
    pcm_samples: np.ndarray,
    *,
    api_key: str,
    workspace: str = "",
    model: str = "qwen3-asr-flash",
    language: str = "zh",
    system_prompt: str = "",
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    base_http_api_url: str = "",
    dashscope_module: Any = None,
) -> str:
    """Recognize one signed-16-bit PCM utterance with Qwen3-ASR-Flash."""
    if len(pcm_samples) < int(sample_rate * MIN_UTTERANCE_SECONDS):
        return ""

    if dashscope_module is None:
        import dashscope as dashscope_module

    if base_http_api_url:
        dashscope_module.base_http_api_url = base_http_api_url

    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_samples.astype("<i2", copy=False).tobytes())
    audio_data = "data:audio/wav;base64," + base64.b64encode(
        wav_buffer.getvalue()
    ).decode("ascii")

    asr_options = {"enable_itn": False}
    normalized_language = str(language or "").strip().lower()
    if normalized_language and normalized_language != "auto":
        asr_options["language"] = normalized_language
    messages = [{"role": "user", "content": [{"audio": audio_data}]}]
    if system_prompt.strip():
        messages.insert(
            0,
            {"role": "system", "content": [{"text": system_prompt.strip()}]},
        )

    response = dashscope_module.MultiModalConversation.call(
        api_key=api_key,
        workspace=workspace or None,
        model=model,
        messages=messages,
        result_format="message",
        asr_options=asr_options,
    )
    return _qwen3_text(response)


def recognize_paraformer(
    pcm_samples: np.ndarray,
    *,
    api_key: str,
    workspace: str = "",
    model: str = "paraformer-realtime-v2",
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> str:
    """Recognize one signed-16-bit PCM utterance with Paraformer."""
    if len(pcm_samples) < int(sample_rate * MIN_UTTERANCE_SECONDS):
        return ""

    from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult

    class _Callback(RecognitionCallback):
        def __init__(self):
            self.final_text = ""
            self.latest_text = ""
            self.error = None

        def on_event(self, result):
            sentence = result.get_sentence()
            if isinstance(sentence, dict):
                text = str(sentence.get("text") or "").strip()
                if text:
                    self.latest_text = text
                    if RecognitionResult.is_sentence_end(sentence):
                        self.final_text = text

        def on_error(self, result):
            self.error = f"{result.code}: {result.message}"

    callback = _Callback()
    pcm_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as pcm_file:
            pcm_path = pcm_file.name
            pcm_file.write(pcm_samples.astype("<i2", copy=False).tobytes())

        import dashscope

        dashscope.api_key = api_key
        recognition = Recognition(
            model=model,
            callback=callback,
            format="pcm",
            sample_rate=sample_rate,
            workspace=workspace or None,
            disfluency_removal_enabled=True,
        )
        result = recognition.call(file=pcm_path)
        sentence = result.get_sentence()
        result_text = ""
        if isinstance(sentence, list):
            result_text = "".join(
                str(item.get("text") or "") for item in sentence if isinstance(item, dict)
            ).strip()
        elif isinstance(sentence, dict):
            result_text = str(sentence.get("text") or "").strip()
        if callback.error:
            print("[ASR] provider=paraformer callback_error", file=sys.stderr, flush=True)
        return result_text or callback.final_text or callback.latest_text
    finally:
        if pcm_path:
            try:
                os.unlink(pcm_path)
            except FileNotFoundError:
                pass


def _recognize_provider(
    provider: str,
    pcm_samples: np.ndarray,
    *,
    api_key: str,
    workspace: str,
    qwen3_model: str,
    paraformer_model: str,
    language: str,
    system_prompt: str,
    sample_rate: int,
    base_http_api_url: str,
) -> str:
    if provider == "qwen3":
        return recognize_qwen3(
            pcm_samples,
            api_key=api_key,
            workspace=workspace,
            model=qwen3_model,
            language=language,
            system_prompt=system_prompt,
            sample_rate=sample_rate,
            base_http_api_url=base_http_api_url,
        )
    if provider == "paraformer":
        return recognize_paraformer(
            pcm_samples,
            api_key=api_key,
            workspace=workspace,
            model=paraformer_model,
            sample_rate=sample_rate,
        )
    raise ValueError(f"unsupported ASR provider: {provider}")


def recognize_utterance(
    pcm_samples: np.ndarray,
    *,
    provider: str = "paraformer",
    fallback_provider: str = "",
    api_key: str,
    workspace: str = "",
    qwen3_model: str = "qwen3-asr-flash",
    paraformer_model: str = "paraformer-realtime-v2",
    language: str = "zh",
    system_prompt: str = "",
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    base_http_api_url: str = "",
) -> str:
    """Recognize with the selected backend and optionally retry through a fallback."""
    primary = provider.strip().lower()
    fallback = fallback_provider.strip().lower()
    if primary not in {"qwen3", "paraformer"}:
        raise ValueError(f"unsupported ASR provider: {provider}")
    if fallback and fallback not in {"qwen3", "paraformer"}:
        raise ValueError(f"unsupported ASR fallback provider: {fallback_provider}")

    common = dict(
        api_key=api_key,
        workspace=workspace,
        qwen3_model=qwen3_model,
        paraformer_model=paraformer_model,
        language=language,
        system_prompt=system_prompt,
        sample_rate=sample_rate,
        base_http_api_url=base_http_api_url,
    )
    try:
        text = _recognize_provider(primary, pcm_samples, **common)
    except Exception as exc:
        print(
            f"[ASR] provider={primary} error={type(exc).__name__}",
            file=sys.stderr,
            flush=True,
        )
        text = ""

    if text or not fallback or fallback == primary:
        return text

    print(
        f"[ASR] provider={primary} empty; fallback={fallback}",
        file=sys.stderr,
        flush=True,
    )
    try:
        return _recognize_provider(fallback, pcm_samples, **common)
    except Exception as exc:
        print(
            f"[ASR] provider={fallback} error={type(exc).__name__}",
            file=sys.stderr,
            flush=True,
        )
        return ""
