import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from framework.honeytoken import Canary, run_pilot


class HoneytokenTest(unittest.TestCase):
    def test_unknown_input_and_duplicate_activation_do_not_add_alerts(self):
        canary = Canary("synthetic-unit-canary")
        for candidate in (None, "incorrect", "x" * 129, "non-ascii-ñ"):
            self.assertEqual(canary.observe(candidate), 404)
        self.assertEqual(canary.events, [])
        self.assertEqual(canary.observe("synthetic-unit-canary"), 204)
        self.assertEqual(canary.observe("synthetic-unit-canary"), 409)
        canary.monitor_once()
        self.assertEqual(canary.observe("synthetic-unit-canary"), 410)
        self.assertEqual([event["phase"] for event in canary.events],
                         ["detected", "alerted", "contained"])

    def test_real_loopback_http_pilot_is_sanitized_and_closes_receiver(self):
        report = run_pilot()
        self.assertTrue(report["passed"])
        self.assertEqual(report["http_statuses"], {"benign": 404, "activation": 204, "replay": 410})
        self.assertFalse(report["real_provider_revocation_measured"])
        self.assertNotIn("feria-canary.", json.dumps(report))
        self.assertGreaterEqual(report["metrics_ns"]["activation_to_local_alert"], 0)
        self.assertGreaterEqual(report["metrics_ns"]["local_alert_to_containment"], 0)

    def test_cli_refuses_existing_report_before_opening_receiver(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.json"
            output.write_text("existing-synthetic-report", encoding="utf-8")
            script = Path(__file__).resolve().parents[1] / "scripts/run_honeytoken_pilot.py"
            result = subprocess.run([sys.executable, str(script), "--output", str(output)],
                                    capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "existing-synthetic-report")
