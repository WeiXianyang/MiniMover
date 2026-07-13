import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import detector


class DetectorTests(unittest.TestCase):
    def test_defaults_are_module_relative(self):
        command = detector.build_command(["--source", "0"])
        self.assertEqual(Path(command[1]), ROOT / "yolov5_runtime" / "detect.py")
        self.assertEqual(
            command[2:6],
            ["--weights", str(ROOT / "model" / "best.pt"), "--output", str(ROOT / "output")],
        )

    def test_command_always_forces_cuda_device_zero(self):
        command = detector.build_command(["--source", "0", "--device", "cpu"])
        self.assertEqual(command[command.index("--device") + 1], "0")
        self.assertEqual(command.count("--device"), 1)

    def test_relative_source_uses_calling_directory(self):
        with patch("detector.Path.cwd", return_value=Path("C:/captures")):
            command = detector.build_command(["--source", "fire.jpg"])
        self.assertEqual(
            Path(command[command.index("--source") + 1]),
            Path("C:/captures/fire.jpg"),
        )

    def test_url_is_unchanged(self):
        source = "rtsp://camera/live"
        command = detector.build_command(["--source", source])
        self.assertEqual(command[command.index("--source") + 1], source)

    def test_car_alias_is_expanded_before_the_legacy_detector_runs(self):
        command = detector.build_command(["--source", "car_A"])
        self.assertEqual(
            command[command.index("--source") + 1],
            "http://192.168.137.23:8080/stream?topic=/camera/color/image_raw",
        )

    def test_live_car_source_enables_preview_unless_explicitly_disabled(self):
        command = detector.build_command(["--source", "car_A"])
        self.assertIn("--view-img", command)

    def test_no_view_is_preserved_for_live_car_source(self):
        command = detector.build_command(["--source", "car_A", "--no-view"])
        self.assertNotIn("--view-img", command)

    @patch("detector.subprocess.run")
    def test_main_returns_child_code(self, run):
        run.return_value.returncode = 7
        self.assertEqual(detector.main(["--source", "0"]), 7)


if __name__ == "__main__":
    unittest.main()
