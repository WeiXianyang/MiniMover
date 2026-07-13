import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "traffic_light"))
import plate_detector


class PlateDetectorTests(unittest.TestCase):
    def test_cli_accepts_car_alias_and_confidence(self):
        arguments = plate_detector.parse_args(["car_B", "--confidence", "0.8"])
        self.assertEqual(arguments.source, "car_B")
        self.assertEqual(arguments.confidence, 0.8)

    @patch("plate_detector.cv2.waitKey")
    @patch("plate_detector.cv2.imshow")
    def test_loading_preview_is_shown_before_model_initialization(self, imshow, wait_key):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        plate_detector.show_loading_preview(frame)
        imshow.assert_called_once()
        wait_key.assert_called_once_with(1)

    @patch("plate_detector.cv2.VideoCapture")
    def test_open_capture_uses_resolved_proxy_url(self, video_capture):
        plate_detector.open_capture("proxy:car_A")
        video_capture.assert_called_once_with("http://localhost:8888/proxy/camera/car_A")

    @patch.dict(sys.modules, {"keras.layers.advanced_activations": None})
    def test_keras_compatibility_module_supports_legacy_hyperlpr_imports(self):
        plate_detector.install_keras_compatibility()
        compatibility_module = sys.modules["keras.layers.advanced_activations"]
        self.assertTrue(hasattr(compatibility_module, "PReLU"))
        from keras import optimizers
        self.assertTrue(hasattr(optimizers, "adam"))

    def test_numpy_compatibility_restores_legacy_float_alias(self):
        import numpy as np
        with patch.object(np, "float", create=True, new=None):
            plate_detector.install_numpy_compatibility()
            self.assertIs(np.float, float)

    def test_opencv_compatibility_normalizes_find_contours_to_legacy_shape(self):
        with patch.object(plate_detector.cv2, "findContours", return_value=("contours", "hierarchy")):
            plate_detector.install_opencv_compatibility()
            self.assertEqual(
                plate_detector.cv2.findContours("image", 1, 2),
                ("image", "contours", "hierarchy"),
            )


if __name__ == "__main__":
    unittest.main()
