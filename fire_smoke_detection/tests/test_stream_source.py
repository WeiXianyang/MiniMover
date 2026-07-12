import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "yolov5_runtime"
sys.path.insert(0, str(RUNTIME))
from utils.datasets import normalize_stream_source


class StreamSourceTests(unittest.TestCase):
    def test_numeric_camera_sources_are_integers(self):
        self.assertEqual(normalize_stream_source("0"), 0)
        self.assertEqual(normalize_stream_source("2"), 2)

    def test_network_stream_sources_stay_strings(self):
        url = "rtsp://camera/live"
        self.assertEqual(normalize_stream_source(url), url)


if __name__ == "__main__":
    unittest.main()
