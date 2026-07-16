import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.fetch_shortmedkg import SHORTMEDKG_COMMIT, download_shortmedkg, verify_sha256


class FetchShortMedKgTests(unittest.TestCase):
    def test_verify_sha256_accepts_only_matching_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "knowledge.jsonl"
            source.write_bytes(b'{"text":"demo"}\n')
            digest = hashlib.sha256(source.read_bytes()).hexdigest()

            self.assertTrue(verify_sha256(source, digest))
            self.assertFalse(verify_sha256(source, "0" * 64))


    @patch("scripts.fetch_shortmedkg.request.urlopen")
    def test_download_writes_validated_snapshot_and_metadata(self, urlopen):
        response = Mock()
        response.read.side_effect = [b'{"text":"demo"}\n', b""]
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        urlopen.return_value = response

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "shortmedkg" / "input_v4.jsonl"
            metadata = download_shortmedkg(output, timeout=2.0)

            self.assertEqual(metadata["commit"], SHORTMEDKG_COMMIT)
            self.assertEqual(metadata["records"], 1)
            self.assertTrue(verify_sha256(output, metadata["sha256"]))
            self.assertEqual(
                __import__("json").loads(
                    output.with_name(output.name + ".metadata.json").read_text(encoding="utf-8")
                )["sha256"],
                metadata["sha256"],
            )


if __name__ == "__main__":
    unittest.main()
