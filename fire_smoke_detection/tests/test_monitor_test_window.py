import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fire_monitor_test_window import (
    build_detector_command,
    format_ai_error,
    read_debug_snapshot,
    stop_process_tree,
)


class MonitorTestWindowTests(unittest.TestCase):
    def test_formats_empty_ai_error_as_none(self):
        self.assertEqual(format_ai_error(""), "\u65e0")
        self.assertEqual(format_ai_error(None), "\u65e0")
        self.assertEqual(format_ai_error("timeout"), "timeout")

    @patch("fire_monitor_test_window.subprocess.run")
    def test_stops_entire_process_tree_on_windows(self, run):
        process = Mock(pid=1234)
        process.poll.return_value = None

        stop_process_tree(process, platform="win32")

        run.assert_called_once_with(
            ["taskkill", "/PID", "1234", "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        process.wait.assert_called_once_with(timeout=5)

    def test_builds_real_camera_and_video_commands(self):
        debug = ROOT / "runtime" / "debug"
        camera = build_detector_command("camera", "2", debug, "cpu")
        self.assertIn("--source", camera)
        self.assertEqual(camera[camera.index("--source") + 1], "2")
        self.assertIn("--no-view", camera)
        self.assertEqual(camera[camera.index("--conf-thres") + 1], "0.7")
        video = build_detector_command("video", "C:/clips/fire demo.mp4", debug, "0")
        self.assertEqual(video[video.index("--source") + 1], str(Path("C:/clips/fire demo.mp4").resolve()))
        self.assertEqual(video[video.index("--device") + 1], "0")

    def test_reads_status_and_only_new_events(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "status.json").write_text(json.dumps({"process": {"state": "running"}}), encoding="utf-8")
            (root / "events.jsonl").write_text('{"stage":"one"}\n{"stage":"two"}\n', encoding="utf-8")
            status, events, offset = read_debug_snapshot(root, 0)
            self.assertEqual(status["process"]["state"], "running")
            self.assertEqual([event["stage"] for event in events], ["one", "two"])
            _, events, offset2 = read_debug_snapshot(root, offset)
            self.assertEqual(events, [])
            self.assertEqual(offset2, offset)


if __name__ == "__main__":
    unittest.main()
