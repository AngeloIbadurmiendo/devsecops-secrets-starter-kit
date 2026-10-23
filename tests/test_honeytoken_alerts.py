from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from framework.honeytoken import Canary, run_pilot
from framework.honeytoken_alerts import deliver_local_alert, receive_local_alert


class HoneytokenAlertTest(unittest.TestCase):
    def test_separate_process_receives_only_sanitized_alert(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "alert.json"
            report = run_pilot(alert_sink=lambda event: deliver_local_alert(output, event))
            self.assertTrue(report["passed"])
            self.assertTrue(report["independent_local_alert_delivered"])
            self.assertFalse(report["external_notification_delivered"])
            receipt = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(set(receipt), {"schema_version", "event_type",
                             "source_event_at_utc", "received_at_utc", "synthetic",
                             "value_retained", "requires_operator_review"})
            self.assertEqual(receipt["source_event_at_utc"], report["events"][1]["at_utc"])
            self.assertFalse(receipt["value_retained"])
            self.assertEqual([event["phase"] for event in report["events"]],
                             ["detected", "alerted", "delivered", "contained"])
            self.assertNotIn("feria-canary.", json.dumps(receipt))

    def test_failed_delivery_still_contains_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.json"
            output.write_text("existing-synthetic-alert", encoding="utf-8")
            report = run_pilot(alert_sink=lambda event: deliver_local_alert(output, event))
            self.assertFalse(report["passed"])
            self.assertFalse(report["independent_local_alert_delivered"])
            self.assertTrue(report["checks"]["replay_blocked"])
            self.assertTrue(report["checks"]["receiver_closed"])
            self.assertEqual(output.read_text(encoding="utf-8"), "existing-synthetic-alert")
        def failing_sink(event):
            raise RuntimeError("synthetic failure")
        canary = Canary("synthetic-unit-canary", alert_sink=failing_sink)
        canary.observe("synthetic-unit-canary")
        canary.monitor_once()
        self.assertTrue(canary.done.is_set())
        self.assertEqual(canary.observe("synthetic-unit-canary"), 410)

    def test_receiver_rejects_extra_fields_and_non_utc_before_writing(self):
        event = {"schema_version": 1, "phase": "alerted", "synthetic": True,
                 "source_event_at_utc": datetime.now(timezone.utc).isoformat()}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "alert.json"
            for payload in (dict(event, unexpected="synthetic-extra-field"),
                            dict(event, source_event_at_utc="2026-09-15T12:00:00"),
                            dict(event, synthetic=False)):
                with self.assertRaises(ValueError):
                    receive_local_alert(output, payload)
                self.assertFalse(output.exists())
