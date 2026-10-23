from __future__ import annotations

import re
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - syntax validation is optional locally
    yaml = None


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
REUSABLE = WORKFLOWS / "reusable-secret-scan.yml"
CALLER = WORKFLOWS / "secret-scan.yml"
SOPS_DEMO = WORKFLOWS / "sops-ci-demo.yml"
OIDC_DEMO = WORKFLOWS / "oidc-login-demo.yml"
AZURE_LIFECYCLE = WORKFLOWS / "azure-lifecycle-demo.yml"


class WorkflowTests(unittest.TestCase):
    def test_workflows_are_valid_yaml_when_pyyaml_is_available(self) -> None:
        if yaml is None:
            self.skipTest("PyYAML is not installed")
        for path in (REUSABLE, CALLER, SOPS_DEMO, OIDC_DEMO, AZURE_LIFECYCLE):
            with self.subTest(path=path.name):
                parsed = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
                self.assertIsInstance(parsed, dict)
                self.assertIn("on", parsed)
                self.assertIn("jobs", parsed)

    def test_reusable_workflow_preserves_security_invariants(self) -> None:
        text = REUSABLE.read_text(encoding="utf-8")
        self.assertIn("workflow_call:", text)
        self.assertIn("contents: read", text)
        self.assertIn("fetch-depth: 0", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("GITLEAKS_VERSION: 8.30.1", text)
        self.assertIn(
            "GITLEAKS_SHA256: 551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
            text,
        )
        self.assertIn("--redact", text)
        self.assertIn('--log-opts="--all"', text)
        self.assertIn("set +e", text)
        self.assertIn("gitleaks-metrics.json", text)
        self.assertIn("report_redacted: true", text)
        self.assertNotIn("secrets:", text)
        self.assertNotRegex(text, re.compile(r"uses:\s+[^\s]+@(main|master|latest)\b"))

    def test_caller_covers_required_events_and_uses_local_workflow(self) -> None:
        text = CALLER.read_text(encoding="utf-8")
        self.assertIn("push:", text)
        self.assertIn("pull_request:", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("uses: ./.github/workflows/reusable-secret-scan.yml", text)
        self.assertIn("contents: read", text)

    def test_sops_demo_is_manual_scoped_and_cleans_sensitive_files(self) -> None:
        text = SOPS_DEMO.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("push:", text)
        self.assertIn("environment: sops-demo", text)
        self.assertIn("contents: read", text)
        self.assertNotIn("id-token: write", text)
        self.assertIn("secrets.SOPS_AGE_KEY", text)
        self.assertIn("SOPS_AGE_KEY_FILE", text)
        self.assertIn("if: always()", text)
        self.assertIn("sops-decrypted.json", text)
        self.assertIn("sops-age-key.txt", text)
        self.assertIn(
            "SOPS_SHA256: e5bec3346a873ae91d871550f3e698c1aad962aff462a080e40f25fde17fef6b",
            text,
        )
        self.assertNotIn("AGE-" + "SECRET-KEY-", text)

    def test_committed_sops_config_has_public_recovery_and_ci_recipients(self) -> None:
        text = (ROOT / ".sops.yaml").read_text(encoding="utf-8")
        recipients = re.findall(r"\bage1[0-9a-z]{58}\b", text)
        self.assertGreaterEqual(len(recipients), 2)
        self.assertEqual(len(recipients), len(set(recipients)))
        self.assertNotIn("AGE-" + "SECRET-KEY-", text)

    def test_oidc_demo_is_manual_environment_scoped_and_secretless(self) -> None:
        text = OIDC_DEMO.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("push:", text)
        self.assertIn("environment: azure-demo", text)
        self.assertIn("contents: read", text)
        self.assertIn("id-token: write", text)
        self.assertIn(
            "azure/login@a641126d1b8aa4d1fa005f4f92df94a3a4c4c906", text
        )
        self.assertIn("secrets.AZURE_CLIENT_ID", text)
        self.assertIn("secrets.AZURE_TENANT_ID", text)
        self.assertIn("secrets.AZURE_SUBSCRIPTION_ID", text)
        self.assertIn("client_secret_used: false", text)
        self.assertIn("identifiers_retained: false", text)
        self.assertIn("if: always()", text)
        self.assertNotIn("client-secret", text.lower())
        self.assertNotIn("actions/checkout", text)
        self.assertNotRegex(text, re.compile(r"uses:\s+[^\s]+@(main|master|latest)\b"))

    def test_azure_lifecycle_is_manual_scoped_and_guarded(self) -> None:
        text = AZURE_LIFECYCLE.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("pull_request:", text)
        self.assertNotIn("push:", text)
        self.assertIn("environment: azure-demo", text)
        self.assertIn("id-token: write", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("--confirm apply:devsecops-kit-demo:dev", text)
        self.assertIn("--what-if", text)
        self.assertIn("framework.starter_kit verify", text)
        self.assertNotIn("client-secret", text.lower())
        self.assertNotIn("framework.starter_kit destroy", text)
        self.assertNotRegex(text, re.compile(r"uses:\s+[^\s]+@(main|master|latest)\b"))


if __name__ == "__main__":
    unittest.main()
