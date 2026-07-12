import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fire_monitor.config import FireMonitorConfig, load_dotenv


class FireMonitorConfigTests(unittest.TestCase):
    def test_defaults_match_approved_design(self):
        with patch.dict(os.environ, {}, clear=True):
            config = FireMonitorConfig.from_env(ROOT)
        self.assertEqual(config.ai_base_url, "https://zz.cxwms.com/v1")
        self.assertEqual(config.ai_endpoint, "/chat/completions")
        self.assertEqual(config.ai_model, "gpt-5.4-mini")
        self.assertEqual(config.trigger_window_seconds, 2.0)
        self.assertEqual(config.trigger_min_hits, 5)
        self.assertEqual(config.event_clear_seconds, 10.0)
        self.assertEqual(config.review_interval_seconds, 30.0)
        self.assertEqual(config.evidence_interval_seconds, 60.0)
        self.assertEqual(config.max_evidence_images, 10)
        self.assertEqual(config.ai_timeout_seconds, 30.0)
        self.assertEqual(config.ai_retries, 2)

    def test_environment_overrides_defaults(self):
        values = {"FIRE_AI_API_KEY": "classroom-key", "FIRE_TRIGGER_MIN_HITS": "7", "FIRE_EVENT_CLEAR_SECONDS": "12.5"}
        with patch.dict(os.environ, values, clear=True):
            config = FireMonitorConfig.from_env(ROOT)
        self.assertEqual(config.ai_api_key, "classroom-key")
        self.assertEqual(config.trigger_min_hits, 7)
        self.assertEqual(config.event_clear_seconds, 12.5)

    def test_dotenv_does_not_override_existing_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("FIRE_AI_API_KEY=file-key\nFIRE_AI_MODEL=file-model\n", encoding="utf-8")
            with patch.dict(os.environ, {"FIRE_AI_API_KEY": "process-key"}, clear=True):
                load_dotenv(env_file)
                self.assertEqual(os.environ["FIRE_AI_API_KEY"], "process-key")
                self.assertEqual(os.environ["FIRE_AI_MODEL"], "file-model")

    def test_endpoint_is_normalized(self):
        with patch.dict(os.environ, {"FIRE_AI_BASE_URL": "https://example/v1/", "FIRE_AI_ENDPOINT": "chat/completions"}, clear=True):
            config = FireMonitorConfig.from_env(ROOT)
        self.assertEqual(config.ai_base_url, "https://example/v1")
        self.assertEqual(config.ai_endpoint, "/chat/completions")

    def test_invalid_positive_values_raise(self):
        with patch.dict(os.environ, {"FIRE_MAX_EVIDENCE_IMAGES": "0"}, clear=True):
            with self.assertRaisesRegex(ValueError, "FIRE_MAX_EVIDENCE_IMAGES"):
                FireMonitorConfig.from_env(ROOT)


if __name__ == "__main__":
    unittest.main()
