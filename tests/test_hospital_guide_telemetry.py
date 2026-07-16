import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from voice_assistant.hospital_guide_telemetry import HospitalGuideTelemetry


class HospitalGuideTelemetryTests(unittest.TestCase):
    def test_publish_writes_a_bounded_safe_snapshot(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.json"
            telemetry = HospitalGuideTelemetry(path, max_events=2)
            telemetry.publish(
                history=[{"role": "user", "content": "带我去内科"}],
                state="WAITING_CONFIRMATION",
                pending_department={
                    "id": "internal_medicine",
                    "name": "内科",
                    "floor": "一层",
                    "navigation_enabled": False,
                },
                evidence_count=3,
                event_type="department_matched",
                event_message="已识别内科，等待用户确认。",
            )
            telemetry.publish(history=[], state="AWAKE", event_type="reply", event_message="第二条")
            telemetry.publish(history=[], state="AWAKE", event_type="reply", event_message="第三条")

            snapshot = telemetry.read()

        self.assertEqual("AWAKE", snapshot["session"]["state"])
        self.assertIsNone(snapshot["session"]["pending_department"])
        self.assertEqual(0, snapshot["knowledge"]["evidence_count"])
        self.assertEqual(["reply", "reply"], [item["type"] for item in snapshot["events"]])
        self.assertFalse(snapshot["navigation"]["requested"])


if __name__ == "__main__":
    unittest.main()
