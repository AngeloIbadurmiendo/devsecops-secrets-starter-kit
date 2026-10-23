import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts.check_no_plaintext_files import PRIVATE_KEY_MARKER, forbidden_reason, main


class PlaintextGuardTests(unittest.TestCase):
    def test_plaintext_names_are_rejected(self):
        for name in (
            ".env",
            ".env.production",
            "local.properties",
            "secrets.plain.yaml",
            "secrets.sops-dec.json",
            "settings.decrypted.yml",
        ):
            with self.subTest(name=name):
                self.assertIsNotNone(forbidden_reason(Path(name)))

    def test_safe_names_are_allowed(self):
        for name in (".env.example", "secrets.enc.yaml", ".sops.yaml"):
            with self.subTest(name=name):
                self.assertIsNone(forbidden_reason(Path(name)))

    def test_private_key_content_is_rejected_without_printing_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "innocent-name.txt"
            private_material = PRIVATE_KEY_MARKER + b"SYNTHETIC-NOT-VALID"
            path.write_bytes(private_material)
            captured = io.StringIO()
            with contextlib.redirect_stderr(captured):
                self.assertEqual(main([str(path)]), 1)
            self.assertEqual(forbidden_reason(path), "age private-key material")
            self.assertNotIn(private_material.decode("ascii"), captured.getvalue())

    def test_private_key_marker_is_detected_across_read_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "boundary.bin"
            split_at = len(PRIVATE_KEY_MARKER) // 2
            path.write_bytes(
                b"x" * (1024 * 1024 - split_at) + PRIVATE_KEY_MARKER + b"invalid"
            )
            self.assertEqual(forbidden_reason(path), "age private-key material")


if __name__ == "__main__":
    unittest.main()
