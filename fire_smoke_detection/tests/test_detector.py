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

    @patch("detector.subprocess.run")
    def test_main_returns_child_code(self, run):
        run.return_value.returncode = 7
        self.assertEqual(detector.main(["--source", "0"]), 7)


if __name__ == "__main__":
    unittest.main()
