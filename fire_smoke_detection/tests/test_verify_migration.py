import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import verify_migration


class VerifyMigrationTests(unittest.TestCase):
    def test_tree_summary_ignores_caches(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data").mkdir()
            (root / "data" / "a.txt").write_text("abc", encoding="utf-8")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "a.pyc").write_bytes(b"ignored")
            self.assertEqual(
                verify_migration.tree_summary(root),
                verify_migration.TreeSummary(1, 3),
            )

    def test_compare_trees_accepts_equal_content(self):
        with tempfile.TemporaryDirectory() as left_temp, tempfile.TemporaryDirectory() as right_temp:
            left = Path(left_temp)
            right = Path(right_temp)
            (left / "x").write_text("same", encoding="utf-8")
            (right / "x").write_text("same", encoding="utf-8")
            self.assertEqual(verify_migration.compare_trees(left, right), [])

    def test_write_checksums_uses_sha256(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "model.pt"
            target.write_bytes(b"model")
            manifest = root / "manifest.txt"
            verify_migration.write_checksums(root, [target], manifest)
            expected = f"{hashlib.sha256(b'model').hexdigest()}  model.pt"
            self.assertEqual(manifest.read_text(encoding="utf-8").strip(), expected)


if __name__ == "__main__":
    unittest.main()
