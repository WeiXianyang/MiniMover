import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fire_monitor.ai_reviewer import AIReviewer, parse_model_content
from fire_monitor.config import FireMonitorConfig
from fire_monitor.types import AIReviewRequest, AIResultKind


class FakeTransport:
    def __init__(self, outcomes): self.outcomes=list(outcomes); self.calls=[]
    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, body, timeout))
        outcome=self.outcomes.pop(0)
        if isinstance(outcome, Exception): raise outcome
        return outcome


def response(content): return {"choices":[{"message":{"content":content}}]}


class AIReviewerTests(unittest.TestCase):
    def config(self, key="key"):
        return FireMonitorConfig(ROOT,"https://example/v1","/chat/completions",key,"model",30,2,2,5,10,30,60,10)

    def request(self): return AIReviewRequest("fire_1",1,b"same-jpeg",datetime.now(timezone.utc))

    def test_parser_accepts_valid_and_code_fence(self):
        kind, confidence, reason = parse_model_content('```json\n{"result":"confirmed_fire","confidence":0.94,"reason":"明确 火焰"}\n```')
        self.assertEqual(kind, AIResultKind.CONFIRMED_FIRE); self.assertEqual(confidence, .94); self.assertEqual(reason,"明确 火焰")

    def test_parser_rejects_invalid_values(self):
        for content in ['{"result":"maybe","confidence":0.5,"reason":"x"}','{"result":"no_fire","confidence":true,"reason":"x"}','{"result":"no_fire","confidence":2,"reason":"x"}']:
            with self.assertRaises(ValueError): parse_model_content(content)

    def test_retries_same_payload_then_succeeds(self):
        transport=FakeTransport([TimeoutError("one"), OSError("two"), response('{"result":"no_fire","confidence":0.7,"reason":"未见火情"}')])
        result=AIReviewer(self.config(),transport).review_now(self.request())
        self.assertTrue(result.success); self.assertEqual(result.attempts,3); self.assertEqual(result.result,AIResultKind.NO_FIRE)
        self.assertEqual(len({call[2] for call in transport.calls}),1)

    def test_all_failures_and_missing_key(self):
        transport=FakeTransport([OSError("secret-body")]*3)
        result=AIReviewer(self.config(),transport).review_now(self.request())
        self.assertFalse(result.success); self.assertEqual(result.attempts,3); self.assertNotIn("same-jpeg",result.error)
        empty=FakeTransport([]); result=AIReviewer(self.config(""),empty).review_now(self.request())
        self.assertEqual(result.attempts,0); self.assertFalse(empty.calls)

    def test_worker_rejects_second_task_and_returns_tagged_result(self):
        reviewer=AIReviewer(self.config(),FakeTransport([response('{"result":"suspected_smoke","confidence":0.8,"reason":"烟雾"}')]))
        self.assertTrue(reviewer.submit(self.request())); self.assertFalse(reviewer.submit(self.request()))
        import time
        deadline=time.time()+1; results=[]
        while time.time()<deadline and not results:
            results=reviewer.poll(); time.sleep(.01)
        reviewer.close(); reviewer.close()
        self.assertEqual(results[0].event_id,"fire_1"); self.assertEqual(results[0].result,AIResultKind.SUSPECTED_SMOKE)


if __name__ == '__main__': unittest.main()
