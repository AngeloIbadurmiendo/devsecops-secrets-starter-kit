import unittest

from framework.sops_demo import render_markdown


class SopsDemoTests(unittest.TestCase):
    def test_markdown_reports_limits_without_sensitive_values(self):
        report = {
            "observed_at_utc": "2026-09-08T00:00:00Z",
            "success": True,
            "tools": {"sops": "3.13.3", "age": "1.3.1"},
            "assertions": {
                "round_trip_matches": True,
                "plaintext_values_absent_from_ciphertext": True,
                "private_key_absent_from_ciphertext": True,
                "private_key_outside_repository": True,
            },
            "timing_ms": {"encrypt": 1.0, "decrypt": 1.0},
            "ephemeral_directory_removed": True,
            "development_deviation": {
                "preliminary_attempts": 1,
                "cause": "Equivalent serialization.",
            },
        }
        markdown = render_markdown(report)
        self.assertIn("Demostración local SOPS con age", markdown)
        self.assertIn("no demuestra todavía", markdown)
        self.assertIn("Desviación de desarrollo", markdown)
        self.assertNotIn("AGE-" + "SECRET-KEY-", markdown)


if __name__ == "__main__":
    unittest.main()
