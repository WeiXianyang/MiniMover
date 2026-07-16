import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from flask import Flask

from hospital_guide_console import register_hospital_guide_console


class HospitalGuideConsoleTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        root = Path(self.directory.name)
        self.runtime_path = root / "runtime.json"
        self.config_path = root / "hospital.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "hospital_name": "\u6f14\u793a\u533b\u9662",
                    "departments": [{
                        "id": "internal_medicine",
                        "name": "\u5185\u79d1",
                        "aliases": ["\u5185\u79d1"],
                        "floor": "\u4e00\u5c42",
                        "directions": "\u8bf7\u524d\u5f80\u5185\u79d1\u5019\u8bca\u533a\u3002",
                        "navigation": {"enabled": False, "x": 0.0, "y": 0.0, "theta": 0.0},
                    }],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.app = Flask(__name__)
        register_hospital_guide_console(self.app, self.runtime_path, self.config_path)
        self.client = self.app.test_client()

    def tearDown(self):
        self.directory.cleanup()

    def test_status_returns_safe_offline_snapshot_when_voice_is_not_running(self):
        response = self.client.get("/api/hospital-guide/status")

        self.assertEqual(200, response.status_code)
        self.assertFalse(response.get_json()["data"]["service_online"])
        self.assertEqual("IDLE", response.get_json()["data"]["session"]["state"])

    def test_console_is_read_only_and_links_to_existing_map_page(self):
        response = self.client.get("/hospital-guide")

        self.assertEqual(200, response.status_code)
        self.assertIn(b'data-console="hospital-guide"', response.data)
        self.assertIn(b"/nav/patrol", response.data)
        self.assertNotIn(b"/api/navigate", response.data)

    def test_favicon_request_returns_no_content_for_a_clean_console(self):
        response = self.client.get("/favicon.ico")

        self.assertEqual(204, response.status_code)

    def test_console_has_anonymized_demo_fields_without_face_or_transcript_data(self):
        from hospital_guide_console import HOSPITAL_GUIDE_CONSOLE_HTML

        self.assertIn("demo-phase-value", HOSPITAL_GUIDE_CONSOLE_HTML)
        self.assertIn("demo-identity-value", HOSPITAL_GUIDE_CONSOLE_HTML)
        self.assertIn("/api/hospital-guide/demo/status", HOSPITAL_GUIDE_CONSOLE_HTML)
        self.assertIn('rel="icon" href="data:,"', HOSPITAL_GUIDE_CONSOLE_HTML)
        self.assertNotIn("confidence", HOSPITAL_GUIDE_CONSOLE_HTML)
        self.assertNotIn("candidates", HOSPITAL_GUIDE_CONSOLE_HTML)
        self.assertNotIn("face_image", HOSPITAL_GUIDE_CONSOLE_HTML)
        self.assertNotIn("data.memory", HOSPITAL_GUIDE_CONSOLE_HTML)
        self.assertNotIn("/api/nav/demo/cancel", HOSPITAL_GUIDE_CONSOLE_HTML)

    def test_public_config_exposes_department_metadata_without_coordinates(self):
        response = self.client.get("/api/hospital-guide/config")
        payload = response.get_json()["data"]

        self.assertEqual("\u6f14\u793a\u533b\u9662", payload["hospital_name"])
        self.assertEqual("\u5185\u79d1", payload["departments"][0]["name"])
        self.assertNotIn("x", payload["departments"][0])


if __name__ == "__main__":
    unittest.main()
