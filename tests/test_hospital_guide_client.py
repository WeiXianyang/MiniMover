import json
import unittest
from unittest.mock import patch

from voice_assistant.hospital_guide_client import HospitalGuideClient


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class HospitalGuideClientTests(unittest.TestCase):
    @patch("voice_assistant.hospital_guide_client.request.urlopen")
    def test_posts_final_text_and_returns_reply(self, urlopen):
        urlopen.return_value = _Response({"code": 0, "data": {"reply": "请确认是否带您去内科。"}})
        client = HospitalGuideClient("http://127.0.0.1:5000", timeout=2)

        reply = client.process_final_text("去内科")

        self.assertEqual("请确认是否带您去内科。", reply)
        req = urlopen.call_args.args[0]
        self.assertEqual("http://127.0.0.1:5000/api/hospital-guide/turn", req.full_url)
        self.assertEqual({"text": "去内科"}, json.loads(req.data.decode("utf-8")))
        self.assertEqual("application/json", req.get_header("Content-type"))

    @patch("voice_assistant.hospital_guide_client.request.urlopen")
    def test_fails_closed_for_error_or_malformed_reply(self, urlopen):
        client = HospitalGuideClient()
        urlopen.return_value = _Response({"code": 1, "msg": "text is required"})
        with self.assertRaisesRegex(RuntimeError, "text is required"):
            client.process_final_text("测试")

        urlopen.return_value = _Response({"code": 0, "data": {"reply": "  "}})
        with self.assertRaisesRegex(RuntimeError, "reply"):
            client.process_final_text("测试")

    def test_rejects_invalid_local_input_before_network(self):
        client = HospitalGuideClient()
        with self.assertRaisesRegex(ValueError, "text"):
            client.process_final_text("  ")


if __name__ == "__main__":
    unittest.main()
