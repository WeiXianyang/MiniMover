import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fire_monitor.ai_reviewer import AIReviewer
from fire_monitor.config import FireMonitorConfig
from fire_monitor.debug_telemetry import DebugTelemetry
from fire_monitor.types import AIReviewRequest


def config(root):
    return FireMonitorConfig(root, "https://example.test/v1", "/chat/completions", "temporary", "model", 30, 2, 2, 5, 10, 30, 60, 10)


class DebugHookTests(unittest.TestCase):
    def test_ai_reviewer_reports_attempt_and_result(self):
        with tempfile.TemporaryDirectory() as directory:
            telemetry = DebugTelemetry(Path(directory))
            attempts = []
            def transport(url, headers, body, timeout):
                attempts.append(body)
                if len(attempts) == 1:
                    raise TimeoutError("timeout")
                return {"choices": [{"message": {"content": '{"result":"no_fire","confidence":0.8,"reason":"测试"}'}}]}
            reviewer = AIReviewer(config(Path(directory)), transport=transport, telemetry=telemetry)
            result = reviewer.review_now(AIReviewRequest("e1", 1, b"same-jpeg", datetime.now(timezone.utc)))
            reviewer.close()
            self.assertTrue(result.success)
            self.assertEqual(result.attempts, 2)
            self.assertEqual(attempts[0], attempts[1])
            events = [json.loads(line) for line in (Path(directory) / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([event["stage"] for event in events], ["ai_attempt", "ai_retry", "ai_attempt", "ai_result"])
            status = json.loads((Path(directory) / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["ai"]["state"], "completed")
            self.assertEqual(status["ai"]["attempt"], 2)


if __name__ == "__main__":
    unittest.main()
