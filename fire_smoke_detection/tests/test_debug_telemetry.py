import json
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fire_monitor.debug_telemetry import DebugTelemetry


class DebugTelemetryTests(unittest.TestCase):
    def test_updates_status_writes_images_and_events(self):
        with tempfile.TemporaryDirectory() as directory:
            telemetry = DebugTelemetry(Path(directory))
            telemetry.update(source="0", detector={"state": "running"})
            telemetry.update(detector={"hit_count": 3})
            frame = np.zeros((12, 16, 3), dtype=np.uint8)
            telemetry.write_image("latest_frame.jpg", frame)
            telemetry.write_jpeg_bytes("latest_ai_upload.jpg", cv2.imencode(".jpg", frame)[1].tobytes())
            telemetry.event("yolo_hit", "fire 0.82", hit_count=3)

            status = json.loads((Path(directory) / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["source"], "0")
            self.assertEqual(status["detector"], {"state": "running", "hit_count": 3})
            self.assertTrue((Path(directory) / "latest_frame.jpg").is_file())
            self.assertTrue((Path(directory) / "latest_ai_upload.jpg").is_file())
            event = json.loads((Path(directory) / "events.jsonl").read_text(encoding="utf-8").strip())
            self.assertEqual(event["stage"], "yolo_hit")
            self.assertEqual(event["hit_count"], 3)

    def test_write_failures_do_not_stop_detection(self):
        class BrokenTelemetry(DebugTelemetry):
            @staticmethod
            def _atomic_json(path, payload):
                raise PermissionError("preview reader holds the file")

        with tempfile.TemporaryDirectory() as directory:
            telemetry = BrokenTelemetry(Path(directory))
            telemetry.update(process={"state": "running"})
            self.assertEqual(telemetry.last_error, "PermissionError: preview reader holds the file")

    def test_rejects_sensitive_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            telemetry = DebugTelemetry(Path(directory))
            with self.assertRaises(ValueError):
                telemetry.update(api_key="secret")
            with self.assertRaises(ValueError):
                telemetry.event("request", "x", authorization="Bearer secret")


if __name__ == "__main__":
    unittest.main()
