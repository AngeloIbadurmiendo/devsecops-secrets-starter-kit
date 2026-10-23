from __future__ import annotations

import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from scripts.verify_sops_ci_demo import VerificationError, verify_demo


class SopsCiDemoTests(unittest.TestCase):
    RECIPIENT_ONE = "age1up2e5vxhmpauhwttqjey7rvk6fqlpgzqtsrq4dynenktdxlavfvq07gcg6"
    RECIPIENT_TWO = "age14qw56pwk8lz0gr2h3lu9enc8h6swak0wz6ud2gfc9ul60jq50gas7259e6"

    def _fixture(self, root: Path, *, leaked: bool = False) -> tuple[Path, Path, Path, Path]:
        decrypted_value = {
            "demo_token": "synthetic-round-trip-value",
            "purpose": "ci-sops-validation",
        }
        canonical = json.dumps(
            decrypted_value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        encrypted_value = {
            "demo_token": "ENC[AES256_GCM,data:redacted]",
            "purpose": "ENC[AES256_GCM,data:redacted]",
            "sops": {
                "age": [
                    {"recipient": self.RECIPIENT_ONE, "enc": "wrapped-one"},
                    {"recipient": self.RECIPIENT_TWO, "enc": "wrapped-two"},
                ]
            },
        }
        if leaked:
            encrypted_value["demo_token"] = decrypted_value["demo_token"]

        decrypted = root / "decrypted.json"
        encrypted = root / "encrypted.json"
        expected = root / "expected.txt"
        metrics = root / "metrics.json"
        decrypted.write_text(json.dumps(decrypted_value), encoding="utf-8")
        encrypted.write_text(json.dumps(encrypted_value), encoding="utf-8")
        expected.write_text(hashlib.sha256(canonical).hexdigest() + "\n", encoding="ascii")
        return encrypted, decrypted, expected, metrics

    def test_verifier_accepts_distinct_recipients_and_writes_safe_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self._fixture(Path(directory))
            report = verify_demo(
                encrypted_path=paths[0],
                decrypted_path=paths[1],
                expected_digest_path=paths[2],
                metrics_path=paths[3],
            )
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["age_recipient_count"], 2)
            self.assertFalse(report["sensitive_values_recorded"])
            persisted = paths[3].read_text(encoding="utf-8")
            self.assertNotIn("synthetic-round-trip-value", persisted)

    def test_verifier_rejects_plaintext_value_in_ciphertext(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self._fixture(Path(directory), leaked=True)
            with self.assertRaises(VerificationError):
                verify_demo(
                    encrypted_path=paths[0],
                    decrypted_path=paths[1],
                    expected_digest_path=paths[2],
                    metrics_path=paths[3],
                )

    def test_verifier_rejects_wrong_semantic_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self._fixture(Path(directory))
            paths[2].write_text("0" * 64 + "\n", encoding="ascii")
            with self.assertRaises(VerificationError):
                verify_demo(
                    encrypted_path=paths[0],
                    decrypted_path=paths[1],
                    expected_digest_path=paths[2],
                    metrics_path=paths[3],
                )

    def test_committed_fixture_contains_only_encrypted_values(self):
        root = Path(__file__).resolve().parents[1]
        encrypted_text = (root / "examples/sops/secrets.enc.json").read_text(
            encoding="utf-8"
        )
        encrypted = json.loads(encrypted_text)
        expected_digest = (
            root / "examples/sops/expected-semantic-sha256.txt"
        ).read_text(encoding="ascii").strip()
        application_values = [
            value for key, value in encrypted.items() if key != "sops"
        ]
        self.assertTrue(application_values)
        self.assertTrue(
            all(
                isinstance(value, str) and value.startswith("ENC[AES256_GCM,")
                for value in application_values
            )
        )
        self.assertRegex(expected_digest, re.compile(r"^[0-9a-f]{64}$"))
        self.assertNotIn("AGE-" + "SECRET-KEY-", encrypted_text)


if __name__ == "__main__":
    unittest.main()
