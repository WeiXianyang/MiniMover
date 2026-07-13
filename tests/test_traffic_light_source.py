import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from traffic_light import detector


class TrafficLightSourceTests(unittest.TestCase):
    def test_source_alias_is_resolved_before_capture_opens(self):
        self.assertEqual(
            detector.resolve_source("car_B"),
            "http://192.168.137.254:8080/stream?topic=/camera/color/image_raw",
        )

    def test_default_detection_thresholds_are_stricter_for_live_video(self):
        vision = detector.TrafficLightDetector()
        self.assertEqual(vision.min_color_ratio, 0.6)
        self.assertEqual(vision.circle_accumulator_threshold, 35)

    def test_detection_thresholds_can_be_customized(self):
        vision = detector.TrafficLightDetector(min_color_ratio=0.75, circle_accumulator_threshold=42)
        self.assertEqual(vision.min_color_ratio, 0.75)
        self.assertEqual(vision.circle_accumulator_threshold, 42)

    @patch("traffic_light.detector.cv2.VideoCapture")
    def test_open_capture_uses_resolved_car_url(self, video_capture):
        detector.open_capture("car_A")
        video_capture.assert_called_once_with(
            "http://192.168.137.23:8080/stream?topic=/camera/color/image_raw"
        )


if __name__ == "__main__":
    unittest.main()
