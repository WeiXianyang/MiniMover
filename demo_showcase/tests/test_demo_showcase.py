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

    def test_every_module_uses_a_real_video_source(self):
        video_extensions = build_videos.VIDEO_EXTENSIONS
        for module in build_videos.MODULES:
            with self.subTest(module=module.key):
                source = build_videos.ASSET_DIR / module.source
                self.assertIn(source.suffix.lower(), video_extensions)
                self.assertTrue(source.is_file(), f"Missing source video: {source}")

    def test_target_specific_sources_are_visible_to_lightweight_detectors(self):
        plate_source = build_videos.ASSET_DIR / "license_plate_source.webm"
        traffic_source = build_videos.ASSET_DIR / "traffic_light_source.webm"
        self.assertGreater(build_videos.count_annotated_frames(plate_source, "plate"), 0)
        self.assertGreater(build_videos.count_annotated_frames(traffic_source, "traffic"), 0)

    def test_fit_frame_produces_640_by_360_frame(self):
        image = np.zeros((100, 300, 3), dtype=np.uint8)
        frame = build_videos.fit_frame(
            image, title="License Plate Recognition", subtitle="Target located"
        )
        self.assertEqual((360, 640, 3), frame.shape)
        self.assertEqual(np.uint8, frame.dtype)

    def test_generated_video_is_readable_and_preserves_real_motion(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.avi"
            output = Path(tmp) / "clip.mp4"
            writer = cv2.VideoWriter(
                str(source), cv2.VideoWriter_fourcc(*"MJPG"), 12, (240, 120)
            )
            self.assertTrue(writer.isOpened())
            for index in range(12):
                frame = np.full((120, 240, 3), 30, dtype=np.uint8)
                cv2.circle(frame, (20 + index * 15, 60), 14, (240, 240, 240), -1)
                writer.write(frame)
            writer.release()

            build_videos.write_clip(
                source,
                output,
                title="Traffic Light Recognition",
                subtitle="REAL VIDEO",
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
            self.assertGreater(build_videos.video_motion_score(output), 1.0)

    def test_repository_sources_have_meaningful_frame_motion(self):
        for module in build_videos.MODULES:
            with self.subTest(module=module.key):
                score = build_videos.video_motion_score(
                    build_videos.ASSET_DIR / module.source
                )
                self.assertGreater(score, 1.0)


class LauncherTests(unittest.TestCase):
    def test_root_launcher_starts_three_independent_players(self):
        root = Path(__file__).resolve().parents[2]
        launcher = (root / "\u4e00\u952e\u542f\u52a8\u4e09\u9879\u8bc6\u522b\u6f14\u793a.bat").read_text(encoding="utf-8-sig")
        self.assertEqual(3, launcher.lower().count('start "demo'))
        self.assertIn("%~dp0", launcher)
        self.assertIn("--check", launcher)
        self.assertNotIn("E:\\MiniMover", launcher)
        self.assertNotIn("timeout /t", launcher.lower())

    def test_answer_defense_readme_exists(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "README.md").read_text(encoding="utf-8")
        self.assertIn("5 \u5206\u949f\u7b54\u8fa9", text)
        self.assertIn("\u4e09\u9879\u8bc6\u522b\u7b54\u8fa9\u6f14\u793a.mp4", text)


if __name__ == "__main__":
    unittest.main()
