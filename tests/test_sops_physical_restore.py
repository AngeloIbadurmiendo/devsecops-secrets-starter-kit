import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from scripts.verify_sops_physical_restore import attempt, isolated_environment


class SopsPhysicalRestoreTest(unittest.TestCase):
    def test_child_environment_excludes_secret_and_default_identity_sources(self):
        with patch.dict(os.environ, {"SOPS_AGE_KEY": "synthetic-not-private",
                                     "SOPS_AGE_KEY_CMD": "forbidden-command",
                                     "SOPS_AGE_SSH_PRIVATE_KEY_FILE": "forbidden-path",
                                     "AWS_SECRET_ACCESS_KEY": "synthetic-placeholder"}):
            environment = isolated_environment(Path("isolated-profile"), Path("restored-copy"))
        self.assertNotIn("SOPS_AGE_KEY", environment)
        self.assertNotIn("SOPS_AGE_KEY_CMD", environment)
        self.assertNotIn("SOPS_AGE_SSH_PRIVATE_KEY_FILE", environment)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", environment)
        self.assertEqual(environment["APPDATA"], environment["USERPROFILE"])
        self.assertEqual(environment["SOPS_DECRYPTION_ORDER"], "age")
        self.assertNotIn("SOPS_AGE_KEY_FILE", isolated_environment(Path("isolated-profile")))

    @patch("scripts.verify_sops_physical_restore.subprocess.run")
    def test_failed_decrypt_suppresses_sensitive_output(self, process):
        process.return_value = subprocess.CompletedProcess([], 1, b"sensitive", b"sensitive")
        result = attempt(Path("fixture"), {}, "0" * 64)
        self.assertFalse(result["decrypted"])
        self.assertNotIn("sensitive", json.dumps(result))
        process.side_effect = subprocess.TimeoutExpired("sensitive", 15, output=b"sensitive")
        self.assertFalse(attempt(Path("fixture"), {}, "0" * 64)["process_completed"])

    @patch("scripts.verify_sops_physical_restore.subprocess.run")
    def test_success_requires_expected_semantic_digest_not_only_exit_zero(self, process):
        process.return_value = subprocess.CompletedProcess([], 0, b'{"synthetic":true}', b"")
        result = attempt(Path("fixture"), {}, "0" * 64)
        self.assertTrue(result["decrypted"])
        self.assertFalse(result["semantic_match"])
