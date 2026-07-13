import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fire_monitor.evidence_store import EvidenceStore


class EvidenceStoreTests(unittest.TestCase):
    def test_save_update_and_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "teacher-note.jpg").write_bytes(b"unknown")
            store = EvidenceStore(root, 10)
            frame = np.zeros((4, 4, 3), dtype=np.uint8)
            paths = []
            base = datetime(2026, 7, 12, tzinfo=timezone.utc)
            for index in range(11):
                paths.append(store.save(f"fire_{index:03d}", 1, "initial", base + timedelta(minutes=index), frame, {"ai_review": {"status": "pending"}}))
            self.assertEqual(len(list(root.glob("fire_*.jpg"))), 10)
            self.assertFalse(paths[0].exists())
            self.assertTrue((root / "teacher-note.jpg").exists())
            latest = paths[-1]
            self.assertTrue(store.update_metadata(latest, {"ai_review": {"status": "completed", "result": "no_fire"}}))
            payload = json.loads(latest.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(payload["ai_review"]["status"], "completed")
            self.assertEqual(payload["ai_review"]["result"], "no_fire")
            self.assertFalse(store.update_metadata(paths[0], {"x": 1}))
            self.assertFalse(list(root.glob("*.tmp")))


if __name__ == "__main__":
    unittest.main()
