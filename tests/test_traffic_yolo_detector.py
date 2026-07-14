import unittest
from pathlib import Path

from traffic_light.yolo_detector import build_command


ROOT = Path(__file__).resolve().parents[1]


class TrafficYoloDetectorTests(unittest.TestCase):
    def test_build_command_uses_car_stream_and_bundled_runtime_paths(self):
        command = build_command("car_A", ["--conf-thres", "0.55"])

        self.assertEqual(command[0], __import__("sys").executable)
        self.assertEqual(
            command[1],
            str(ROOT / "traffic_light" / "Traffic-Light-Detection-Using-YOLOv3" / "detect.py"),
        )
        self.assertIn("http://192.168.137.23:8080/stream?topic=/camera/color/image_raw", command)
        self.assertIn(str(ROOT / "traffic_light" / "Traffic-Light-Detection-Using-YOLOv3" / "weights" / "best_model_12.pt"), command)
        self.assertEqual(command[-2:], ["--conf-thres", "0.55"])

    def test_build_command_enables_view_for_remote_stream(self):
        command = build_command("car_B", [])
        self.assertIn("--view-img", command)
        self.assertIn("--img-size", command)
        self.assertIn("608", command)


if __name__ == "__main__":
    unittest.main()
