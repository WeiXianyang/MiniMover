import json
import unittest
from unittest.mock import Mock, patch

from voice_assistant.car_client import CarClient
from voice_assistant.command_parser import parse_command
from voice_assistant.voice_service import VoiceService
from voice_assistant.speaker_verifier import cosine_similarity
from voice_assistant.wake_word import WakeWordVoiceService


class CommandParserTests(unittest.TestCase):
    def test_parses_supported_commands(self):
        self.assertEqual(parse_command("\u8bf7\u5411\u5de6\u8f6c"), {"cmd": "left"})
        self.assertEqual(parse_command("\u505c\u4e0b\u6765"), {"cmd": "stop"})
        self.assertEqual(parse_command("\u6025\u505c\uff0c\u4e0d\u8981\u52a8"), {"cmd": "stop"})
        self.assertEqual(parse_command("\u5411\u53f3\u8f6c\u4e00\u4e0b"), {"cmd": "right"})
        self.assertEqual(parse_command("\u5411\u540e\u8f6c"), {"cmd": "backward"})
        self.assertEqual(parse_command("\u539f\u5730\u8f6c\u5708"), {"cmd": "spin"})
        self.assertEqual(parse_command("\u7ed9\u6211\u8df3\u4e2a\u821e"), {"cmd": "dance"})

    def test_rejects_unsupported_text(self):
        self.assertIsNone(parse_command("\u8bf7\u544a\u8bc9\u6211\u73b0\u5728\u51e0\u70b9"))


class SpeakerVerifierTests(unittest.TestCase):
    def test_cosine_similarity(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [1, 0]), 1.0)
        self.assertAlmostEqual(cosine_similarity([1, 0], [0, 1]), 0.0)


class VoiceServiceTests(unittest.TestCase):

    def test_question_uses_llm_and_tts_without_moving(self):
        car = Mock()
        llm = Mock()
        llm.answer.return_value = "\u6211\u53ef\u4ee5\u5e2e\u4f60\u3002"
        tts = Mock()
        service = VoiceService(car, Mock(), llm_client=llm, tts_backend=tts)
        service.handle_final({"type": "final_text", "text": "\u4f60\u662f\u8c01"})
        llm.answer.assert_called_once_with("\u4f60\u662f\u8c01")
        tts.speak.assert_called_once_with("\u6211\u53ef\u4ee5\u5e2e\u4f60\u3002")
        car.execute.assert_not_called()

    def test_unsupported_text_does_not_move(self):
        car = Mock()
        service = VoiceService(car, Mock())
        service.handle_final({"type": "final_text", "text": "今天天气怎么样"})
        car.execute.assert_not_called()

    def test_stop_has_highest_priority(self):
        car = Mock()
        llm = Mock()
        service = VoiceService(car, Mock(), llm_client=llm)
        service.handle_final({"type": "final_text", "text": "\u6025\u505c"})
        car.execute.assert_called_once_with({"cmd": "stop"}, 35, 0)
        llm.answer.assert_not_called()

    def test_unverified_speaker_cannot_move(self):
        car = Mock()
        verifier = Mock()
        verifier.verify.return_value = {"verified": False, "similarity": 0.2}
        service = VoiceService(car, Mock(), speaker_verifier=verifier)
        service.handle_final({"type": "final_text", "text": "\u5411\u5de6\u8f6c", "samples": [1] * 16000})
        car.execute.assert_not_called()

    def test_verified_speaker_can_move(self):
        car = Mock()
        verifier = Mock()
        verifier.verify.return_value = {"verified": True, "similarity": 0.8}
        service = VoiceService(car, Mock(), speaker_verifier=verifier)
        service.handle_final({"type": "final_text", "text": "\u5411\u5de6\u8f6c", "samples": [1] * 16000})
        car.execute.assert_called_once_with({"cmd": "left"}, 35, 0.8)

    def test_shutdown_stops_car_and_tts(self):
        car = Mock()
        tts = Mock()
        service = VoiceService(car, Mock(), tts_backend=tts)
        service.stop()
        car.execute.assert_called_once_with({"cmd": "stop"}, 35, 0)
        tts.stop.assert_called_once_with()

    def test_supported_text_moves_once(self):
        car = Mock()
        service = VoiceService(car, Mock(), speed=20, duration=0.5)
        service.handle_final({"type": "final_text", "text": "请向右转"})
        car.execute.assert_called_once_with({"cmd": "right"}, 20, 0.5)

    def test_dance_command_starts_motion_sequence(self):
        car = Mock()
        service = VoiceService(car, Mock())
        service.handle_final({"type": "final_text", "text": "\u6765\u8df3\u4e2a\u821e"})
        car.execute_dance.assert_called_once_with()
        car.execute.assert_not_called()


class WakeWordVoiceServiceTests(unittest.TestCase):
    def test_wake_word_resets_conversation_at_session_boundaries(self):
        voice = Mock()
        voice.tts_backend = None
        service = WakeWordVoiceService(
            voice, wake_word="wake", greeting="hello", idle_timeout=1.0
        )

        with patch("voice_assistant.wake_word.time.monotonic", return_value=10.0):
            service._on_final({"text": "wake"})
        voice.reset_conversation.assert_called_once_with()

        with patch("voice_assistant.wake_word.time.monotonic", return_value=12.0):
            service._on_final({"text": "later"})
        self.assertEqual(voice.reset_conversation.call_count, 2)

class CarClientTests(unittest.TestCase):
    @patch("voice_assistant.car_client.request.urlopen")
    def test_posts_safe_move_payload(self, urlopen):
        response = Mock()
        response.read.return_value = json.dumps({"code": 0}).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        urlopen.return_value = response

        result = CarClient("http://127.0.0.1:6500").execute(
            {"cmd": "left"}, speed=35, duration=0.8
        )

        self.assertEqual(result["code"], 0)
        payload = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload, {"cmd": "left", "speed": 35, "duration": 0.8})


if __name__ == "__main__":
    unittest.main()
