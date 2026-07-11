import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from demo_showcase import build_videos, player


class PlayerTests(unittest.TestCase):
    def test_resolve_video_uses_supplied_base_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            expected = Path(tmp) / "videos" / "demo.mp4"
            actual = player.resolve_video("videos/demo.mp4", Path(tmp))
            self.assertEqual(expected.resolve(), actual)

    def test_validate_video_rejects_missing_file(self):
        with self.assertRaisesRegex(FileNotFoundError, "Demo video not found"):
            player.validate_video(Path("definitely-missing-demo.mp4"))

    def test_parser_has_answer_defense_defaults(self):
        args = player.build_parser().parse_args(["sample.mp4"])
        self.assertEqual("Recognition Demo", args.title)
        self.assertEqual(40, args.x)
        self.assertEqual(40, args.y)
        self.assertTrue(args.loop)


class VideoBuilderTests(unittest.TestCase):
    def test_defines_exactly_three_independent_modules(self):
        self.assertEqual(
            ["license_plate", "traffic_light", "fire_smoke"],
            [item.key for item in build_videos.MODULES],
        )

    def test_fit_frame_produces_640_by_360_frame(self):
        image = np.zeros((100, 300, 3), dtype=np.uint8)
        frame = build_videos.fit_frame(
            image, title="License Plate Recognition", subtitle="Target located"
        )
        self.assertEqual((360, 640, 3), frame.shape)
        self.assertEqual(np.uint8, frame.dtype)

    def test_generated_video_is_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "clip.mp4"
            image = np.full((120, 240, 3), 80, dtype=np.uint8)
            build_videos.write_clip(
                image,
                output,
                title="Traffic Light Recognition",
                subtitle="RED LIGHT",
                seconds=1,
                fps=12,
            )
            capture = cv2.VideoCapture(str(output))
            try:
                self.assertTrue(capture.isOpened())
                self.assertGreaterEqual(int(capture.get(cv2.CAP_PROP_FRAME_COUNT)), 12)
                ok, frame = capture.read()
                self.assertTrue(ok)
                self.assertEqual((360, 640, 3), frame.shape)
            finally:
                capture.release()


if __name__ == "__main__":
    unittest.main()
