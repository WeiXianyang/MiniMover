import base64
import io
import sys
import types
import unittest
import wave
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from voice_assistant.asr_backends import (
    recognize_paraformer,
    recognize_qwen3,
    recognize_utterance,
)


class _FakeDashScope:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.MultiModalConversation = SimpleNamespace(call=Mock(side_effect=self._call))

    def _call(self, **kwargs):
        if self._error is not None:
            raise self._error
        return self._response


class AsrBackendsTests(unittest.TestCase):
    def setUp(self):
        self.samples = np.arange(6400, dtype=np.int16)

    def test_qwen3_wraps_pcm_as_base64_wav_and_parses_text(self):
        response = {
            "status_code": 200,
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": [{"text": "带我去内科"}],
                        }
                    }
                ]
            },
        }
        dashscope_module = _FakeDashScope(response=response)
        captured_audio = {}

        def inspect_call(**kwargs):
            audio_data = kwargs["messages"][0]["content"][0]["audio"]
            self.assertTrue(audio_data.startswith("data:audio/wav;base64,"))
            encoded = audio_data.split(",", 1)[1]
            with wave.open(io.BytesIO(base64.b64decode(encoded)), "rb") as wav_file:
                captured_audio.update(
                    channels=wav_file.getnchannels(),
                    sample_width=wav_file.getsampwidth(),
                    sample_rate=wav_file.getframerate(),
                    frames=wav_file.getnframes(),
                )
            return response

        dashscope_module.MultiModalConversation.call.side_effect = inspect_call

        text = recognize_qwen3(
            self.samples,
            api_key="test-key",
            workspace="ws-test",
            model="qwen3-asr-flash",
            language="zh",
            dashscope_module=dashscope_module,
        )

        self.assertEqual("带我去内科", text)
        self.assertEqual(
            {
                "channels": 1,
                "sample_width": 2,
                "sample_rate": 16000,
                "frames": len(self.samples),
            },
            captured_audio,
        )
        kwargs = dashscope_module.MultiModalConversation.call.call_args.kwargs
        self.assertEqual("qwen3-asr-flash", kwargs["model"])
        self.assertEqual("ws-test", kwargs["workspace"])
        self.assertEqual({"language": "zh", "enable_itn": False}, kwargs["asr_options"])


    def test_qwen3_sends_optional_hospital_context_as_system_message(self):
        response = {
            "status_code": 200,
            "output": {
                "choices": [
                    {"message": {"content": [{"text": "\u5185\u79d1"}]}}
                ]
            },
        }
        dashscope_module = _FakeDashScope(response=response)
        prompt = "\u533b\u9662\u5bfc\u8bca\u573a\u666f\uff0c\u91cd\u70b9\u8bc6\u522b\u5185\u79d1\u548c\u5916\u79d1\u3002"

        text = recognize_qwen3(
            self.samples,
            api_key="test-key",
            system_prompt=prompt,
            dashscope_module=dashscope_module,
        )

        self.assertEqual("\u5185\u79d1", text)
        messages = dashscope_module.MultiModalConversation.call.call_args.kwargs["messages"]
        self.assertEqual(
            {"role": "system", "content": [{"text": prompt}]},
            messages[0],
        )
        self.assertIn("audio", messages[1]["content"][0])

    def test_paraformer_removes_temporary_pcm_after_success(self):
        asr_module = types.ModuleType("dashscope.audio.asr")

        class RecognitionCallback:
            pass

        class RecognitionResult:
            @staticmethod
            def is_sentence_end(_sentence):
                return True

        class Result:
            @staticmethod
            def get_sentence():
                return {"text": "\u5e26\u6211\u53bb\u5185\u79d1"}

        class Recognition:
            def __init__(self, **_kwargs):
                pass

            @staticmethod
            def call(**_kwargs):
                return Result()

        asr_module.Recognition = Recognition
        asr_module.RecognitionCallback = RecognitionCallback
        asr_module.RecognitionResult = RecognitionResult
        dashscope_module = types.ModuleType("dashscope")
        audio_module = types.ModuleType("dashscope.audio")
        dashscope_module.audio = audio_module
        audio_module.asr = asr_module

        with patch.dict(
            sys.modules,
            {
                "dashscope": dashscope_module,
                "dashscope.audio": audio_module,
                "dashscope.audio.asr": asr_module,
            },
        ):
            text = recognize_paraformer(self.samples, api_key="test-key")

        self.assertEqual("\u5e26\u6211\u53bb\u5185\u79d1", text)

    @patch("voice_assistant.asr_backends.recognize_paraformer", return_value="带我去内科")
    @patch("voice_assistant.asr_backends.recognize_qwen3", return_value="")
    def test_qwen3_empty_text_falls_back_to_paraformer(self, qwen3, paraformer):
        text = recognize_utterance(
            self.samples,
            provider="qwen3",
            fallback_provider="paraformer",
            api_key="test-key",
            workspace="ws-test",
        )

        self.assertEqual("带我去内科", text)
        qwen3.assert_called_once()
        paraformer.assert_called_once()

    @patch("voice_assistant.asr_backends.recognize_paraformer", return_value="带我去内科")
    @patch("voice_assistant.asr_backends.recognize_qwen3", side_effect=RuntimeError("request failed"))
    def test_qwen3_error_falls_back_without_propagating(self, qwen3, paraformer):
        text = recognize_utterance(
            self.samples,
            provider="qwen3",
            fallback_provider="paraformer",
            api_key="test-key",
            workspace="ws-test",
        )

        self.assertEqual("带我去内科", text)
        qwen3.assert_called_once()
        paraformer.assert_called_once()

    @patch("voice_assistant.asr_backends.recognize_paraformer", return_value="??")
    @patch("voice_assistant.asr_backends.recognize_qwen3")
    def test_safe_default_remains_paraformer_without_fallback(self, qwen3, paraformer):
        text = recognize_utterance(
            self.samples,
            api_key="test-key",
            workspace="ws-test",
        )

        self.assertEqual("??", text)
        qwen3.assert_not_called()
        paraformer.assert_called_once()

    @patch("voice_assistant.asr_backends.recognize_paraformer", return_value="内科")
    @patch("voice_assistant.asr_backends.recognize_qwen3")
    def test_paraformer_remains_selectable(self, qwen3, paraformer):
        text = recognize_utterance(
            self.samples,
            provider="paraformer",
            fallback_provider="",
            api_key="test-key",
            workspace="ws-test",
        )

        self.assertEqual("内科", text)
        qwen3.assert_not_called()
        paraformer.assert_called_once()

    def test_rejects_unknown_provider(self):
        with self.assertRaisesRegex(ValueError, "unsupported ASR provider"):
            recognize_utterance(
                self.samples,
                provider="unknown",
                fallback_provider="",
                api_key="test-key",
                workspace="ws-test",
            )


if __name__ == "__main__":
    unittest.main()
