import unittest
from unittest.mock import patch

from scripts.collect_functions_diagnostics import collect, signal_categories
from scripts.collect_functions_diagnostics import query
import subprocess


class FunctionsDiagnosticsTest(unittest.TestCase):
    def test_raw_message_is_reduced_to_categories(self):
        raw = "ModuleNotFoundError: No module named synthetic_dependency; private detail omitted"
        categories = signal_categories(raw)
        self.assertEqual(categories, ["missing_python_module"])
        self.assertNotIn("synthetic_dependency", repr(categories))
        self.assertEqual(signal_categories("unrecognized confidential detail"), [])
        self.assertEqual(signal_categories(
            "The route template separator character '/' cannot appear consecutively."),
            ["invalid_consecutive_route_separator"])

    @patch("scripts.collect_functions_diagnostics.subprocess.run")
    def test_successful_detector_catalog_is_not_treated_as_observed_errors(self, run):
        run.return_value = subprocess.CompletedProcess([], 0,
            '{"description": "Troubleshoot service unavailable 503 or access denied"}', "")
        data, metadata = query("rest", "--method", "get", "--url", "https://example.invalid")
        self.assertIsNotNone(data)
        self.assertTrue(metadata["query_passed"])
        self.assertEqual(metadata["categories"], [])

    @patch("scripts.collect_functions_diagnostics.required")
    def test_foreign_group_is_rejected_before_application_queries(self, required):
        required.side_effect = [
            {"id": "synthetic-account"},
            {"state": "Enabled", "subscriptionPolicies": {
                "quotaId": "AzureForStudents_2018-01-01", "spendingLimit": "On"}},
            {"location": "brazilsouth", "tags": {"purpose": "unrelated"}},
        ]
        with self.assertRaisesRegex(ValueError, "ownership guard"):
            collect({"project_name": "synthetic", "environment": "test",
                     "expires_on": "2099-01-01", "azure_location": "brazilsouth"},
                    "rg-synthetic")
        self.assertEqual(required.call_count, 3)
