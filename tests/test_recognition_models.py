import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_recognition_models import inspect_model_file, load_manifest


ROOT = Path(__file__).resolve().parents[1]


class RecognitionModelManifestTests(unittest.TestCase):
    def test_manifest_declares_all_three_recognition_models(self):
        manifest = load_manifest(ROOT / "recognition_models.json")

        self.assertEqual(
            set(manifest["models"]),
            {"fire_smoke", "traffic_light_yolo", "license_plate_hyperlpr"},
        )
        self.assertEqual(
            manifest["models"]["fire_smoke"]["sha256"],
            "d1eae6859229ac1f5699c60f9445fa054dafc6a2cc59f00fc30ea6379dc3247e",
        )
        self.assertEqual(
            manifest["models"]["traffic_light_yolo"]["size"], 250783600
        )
        self.assertTrue(
            manifest["models"]["traffic_light_yolo"]["download_url"].startswith("https://")
        )
        self.assertEqual(
            manifest["models"]["license_plate_hyperlpr"]["license"], "Apache-2.0"
        )

    def test_inspect_model_file_detects_valid_missing_pointer_and_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = b"model-bytes"
            expected = hashlib.sha256(payload).hexdigest()
            model = root / "model.pt"

            self.assertEqual(inspect_model_file(model, len(payload), expected)["status"], "missing")

            model.write_bytes(payload)
            self.assertEqual(inspect_model_file(model, len(payload), expected)["status"], "ok")

            model.write_text(
                "version https://git-lfs.github.com/spec/v1\n"
                "oid sha256:abc\nsize 123\n",
                encoding="utf-8",
            )
            self.assertEqual(inspect_model_file(model, 123, "abc")["status"], "lfs_pointer")

            model.write_bytes(b"wrong")
            self.assertEqual(inspect_model_file(model, len(payload), expected)["status"], "mismatch")


if __name__ == "__main__":
    unittest.main()
