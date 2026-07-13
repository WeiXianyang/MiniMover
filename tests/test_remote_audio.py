import json
import unittest
from unittest.mock import Mock, patch

from voice_assistant.car_audio_client import CarAudioClient
from voice_assistant.remote_audio_backend import transcribe_wav


class CarAudioClientTests(unittest.TestCase):
    @patch("voice_assistant.car_audio_client.request.urlopen")
    def test_record_stops_and_downloads_wav(self, urlopen):
        responses = []
        for payload in (
            {"code": 0, "data": {"record_id": "abc123"}},
            {"code": 0, "data": {"status": "done"}},
            {"code": 0, "data": {"record_id": "abc123"}},
        ):
            response = Mock()
            response.read.return_value = json.dumps(payload).encode()
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            responses.append(response)
        wav = Mock()
        wav.read.return_value = b"RIFF-wav"
        wav.__enter__ = Mock(return_value=wav)
        wav.__exit__ = Mock(return_value=False)
        responses.append(wav)
        urlopen.side_effect = responses

        result = CarAudioClient("http://car", poll_interval=0).record(0)
        self.assertEqual(result, ("abc123", b"RIFF-wav"))
        self.assertEqual(urlopen.call_count, 4)


class RemoteAudioTests(unittest.TestCase):
    @patch("voice_assistant.remote_audio_backend.request.urlopen")
    def test_transcribe_wav_posts_multipart_audio(self, urlopen):
        response = Mock()
        response.read.return_value = '{"text":"向左转"}'.encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        urlopen.return_value = response

        self.assertEqual(transcribe_wav("http://asr/v1", "key", "whisper-1", b"wav"), "向左转")
        request_object = urlopen.call_args.args[0]
        self.assertIn(b'filename="speech.wav"', request_object.data)
        self.assertIn(b"wav", request_object.data)


if __name__ == "__main__":
    unittest.main()
