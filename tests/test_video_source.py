import unittest
from unittest.mock import patch

from video_source import resolve_source


class VideoSourceTests(unittest.TestCase):
    def test_car_aliases_resolve_to_direct_low_latency_streams(self):
        self.assertEqual(
            resolve_source("car_A"),
            "http://192.168.137.23:8080/stream?topic=/camera/color/image_raw",
        )
        self.assertEqual(
            resolve_source("car_B"),
            "http://192.168.43.8:6500/video_feed",
        )

    def test_proxy_aliases_resolve_through_coordination_center(self):
        self.assertEqual(
            resolve_source("proxy:car_A"),
            "http://localhost:8888/proxy/camera/car_A",
        )
        self.assertEqual(
            resolve_source("proxy:car_B"),
            "http://localhost:8888/proxy/camera/car_B",
        )

    def test_non_alias_sources_are_preserved(self):
        for source in ("0", "capture.mp4", "http://example.test/live"):
            with self.subTest(source=source):
                self.assertEqual(resolve_source(source), source)

    def test_aliases_are_case_insensitive_and_surrounding_whitespace_is_ignored(self):
        self.assertEqual(
            resolve_source(" CAR_a "),
            "http://192.168.137.23:8080/stream?topic=/camera/color/image_raw",
        )


if __name__ == "__main__":
    unittest.main()
