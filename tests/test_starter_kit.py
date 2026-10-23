import contextlib
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from framework.starter_kit.cli import main
from framework.starter_kit.config import (
    ConfigurationError,
    ProjectConfig,
    is_valid_age_recipient,
    read_config,
    write_config,
)
from framework.starter_kit.doctor import doctor_report
from framework.starter_kit.generator import GenerationConflictError, generate_project
from framework.starter_kit.lifecycle import (
    LifecycleError,
    apply_environment,
    destroy_environment,
    verify_environment,
)
from framework.starter_kit.planner import PlanError, build_plan


class StarterKitTests(unittest.TestCase):
    RECIPIENT_ONE = "age1up2e5vxhmpauhwttqjey7rvk6fqlpgzqtsrq4dynenktdxlavfvq07gcg6"
    RECIPIENT_TWO = "age14qw56pwk8lz0gr2h3lu9enc8h6swak0wz6ud2gfc9ul60jq50gas7259e6"

    def test_configuration_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "feria-project.json"
            expected = ProjectConfig(project_name="proyecto-feria")
            write_config(path, expected)
            self.assertEqual(expected, read_config(path))

    def test_invalid_project_name_is_rejected(self):
        with self.assertRaises(ConfigurationError):
            ProjectConfig(project_name="Pyro Prev").validate()

    def test_only_preflight_selected_region_is_allowed(self):
        with self.assertRaises(ConfigurationError):
            ProjectConfig(
                project_name="proyecto-feria", azure_location="chilecentral"
            ).validate()

    def test_only_preflight_selected_compute_profile_is_allowed(self):
        with self.assertRaises(ConfigurationError):
            ProjectConfig(
                project_name="proyecto-feria", compute_profile="pending-preflight"
            ).validate()

    def test_age_recipient_checksum_is_validated(self):
        self.assertTrue(is_valid_age_recipient(self.RECIPIENT_ONE))
        changed_checksum = self.RECIPIENT_ONE[:-1] + "q"
        self.assertFalse(is_valid_age_recipient(changed_checksum))
        with self.assertRaises(ConfigurationError):
            ProjectConfig(
                project_name="proyecto-feria",
                sops_age_recipients=(changed_checksum,),
            ).validate()

    def test_duplicate_age_recipients_are_rejected(self):
        with self.assertRaises(ConfigurationError):
            ProjectConfig(
                project_name="proyecto-feria",
                sops_age_recipients=(self.RECIPIENT_ONE, self.RECIPIENT_ONE),
            ).validate()

    def test_doctor_report_is_read_only_and_structured(self):
        report = doctor_report("local")
        self.assertTrue(report["remote_changes_performed"] is False)
        self.assertEqual(report["schema_version"], 1)
        self.assertIn("python", [tool["name"] for tool in report["tools"]])

    def test_cloud_doctor_includes_g2_toolchain(self):
        report = doctor_report("cloud")
        required = {
            tool["name"] for tool in report["tools"] if tool["required"]
        }
        self.assertTrue({"azd", "sops", "age", "bicep"}.issubset(required))

    def test_generation_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            config = ProjectConfig(project_name="proyecto-feria")
            first_manifest = generate_project(config, output)
            first_hashes = self._tree_hashes(output)
            second_manifest = generate_project(config, output)
            second_hashes = self._tree_hashes(output)
            self.assertEqual(first_manifest, second_manifest)
            self.assertEqual(first_hashes, second_hashes)
            self.assertIn(".github/workflows/secret-scan.yml", first_manifest["files"])
            self.assertIn("infra/bicep/main.bicep", first_manifest["files"])
            self.assertIn("README.md", first_manifest["files"])
            self.assertIn("app/health.py", first_manifest["files"])
            self.assertIn("function_app.py", first_manifest["files"])
            self.assertIn("tests/test_app.py", first_manifest["files"])
            self.assertNotIn(
                ".github/workflows/azure-lifecycle-demo.yml", first_manifest["files"]
            )
            self.assertIn(
                "infra/bicep/modules/functions-flex-python.bicep",
                first_manifest["files"],
            )
            self.assertFalse(first_manifest["remote_changes_performed"])

    def test_generation_refuses_to_overwrite_modified_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "SECURITY.md").write_text("user content\n", encoding="utf-8")
            with self.assertRaises(GenerationConflictError):
                generate_project(ProjectConfig(project_name="proyecto-feria"), output)
            self.assertFalse((output / ".gitleaks.toml").exists())

    def test_generation_does_not_overwrite_team_application_code(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            config = ProjectConfig(project_name="proyecto-feria")
            generate_project(config, output)
            app_code = output / "app/health.py"
            app_code.write_text("# Team code\n", encoding="utf-8")
            with self.assertRaises(GenerationConflictError):
                generate_project(config, output)
            self.assertEqual(app_code.read_text(encoding="utf-8"), "# Team code\n")

    def test_generated_application_smoke_without_cloud_or_sdk(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            manifest = generate_project(ProjectConfig(project_name="proyecto-feria"), output)
            completed = subprocess.run(
                [sys.executable, "-E", "-S", "-B", "-m", "unittest", "discover",
                 "-s", "tests", "-p", "test_*.py"],
                cwd=output, capture_output=True, text=True, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("README.md", manifest["files"])
            self.assertTrue((output / "function_app.py").is_file())
            self.assertFalse((output / ".github/workflows/oidc-login-demo.yml").exists())
            self.assertTrue((output / "examples/azure-workflows/oidc-login-demo.yml").is_file())
            self.assertIn("local.settings.json", (output / ".gitignore").read_text(encoding="utf-8"))
            self.assertIn(
                "forbid-functions-local-settings",
                (output / ".pre-commit-config.yaml").read_text(encoding="utf-8"),
            )
            blocked = subprocess.run(
                [sys.executable, "-E", "-S", "-B",
                 str(output / "scripts/check_local_settings.py"), "local.settings.json"],
                cwd=output, capture_output=True, text=True, check=False,
            )
            self.assertEqual(blocked.returncode, 1)
            self.assertNotIn("SECRET", blocked.stderr)

    def test_manifest_conflict_does_not_write_any_generated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            manifest = output / ".feria/manifest.json"
            manifest.parent.mkdir()
            manifest.write_text("user-owned manifest\n", encoding="utf-8")
            before = self._tree_hashes(output)
            with self.assertRaises(GenerationConflictError):
                generate_project(ProjectConfig(project_name="proyecto-feria"), output)
            self.assertEqual(before, self._tree_hashes(output))

    def test_generated_runtime_can_regenerate_without_source_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "generated"
            replica = root / "replica"
            generate_project(ProjectConfig(project_name="proyecto-feria"), output)
            command = [sys.executable, "-E", "-S", "-B"]
            origin = subprocess.run(
                command + ["-c", (
                    "from pathlib import Path; import framework.starter_kit.cli as c; "
                    "assert Path(c.__file__).resolve().is_relative_to(Path.cwd()); "
                    "print('generated-runtime-origin-confirmed')"
                )],
                cwd=output, capture_output=True, text=True, check=False,
            )
            self.assertEqual(origin.returncode, 0, origin.stderr)
            self.assertIn("origin-confirmed", origin.stdout)
            for _ in range(2):
                completed = subprocess.run(
                    command + ["-m", "framework.starter_kit", "generate",
                               "--output", str(replica)],
                    cwd=output, capture_output=True, text=True, check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(self._tree_hashes(output), self._tree_hashes(replica))

    @unittest.skipUnless(shutil.which("az"), "Azure CLI is not installed")
    def test_generated_runtime_compiles_local_plan_without_source_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            generate_project(ProjectConfig(
                project_name="proyecto-feria", expires_on="2099-12-31",
            ), output)
            # Azure CLI/Bicep can retain a Windows working-directory handle.
            # Import only the generated runtime but launch from the stable checkout.
            completed = subprocess.run(
                [sys.executable, "-E", "-S", "-B", "-c", (
                    "import sys; from pathlib import Path; "
                    "root = Path(sys.argv.pop(1)); sys.path.insert(0, str(root)); "
                    "import framework.starter_kit.cli as c; "
                    "assert Path(c.__file__).resolve().is_relative_to(root); "
                    "raise SystemExit(c.main(sys.argv[1:]))"
                ), str(output), "plan", "--config", str(output / "feria-project.json"),
                 "--output", str(output / ".feria/plan.json")],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            plan = json.loads((output / ".feria/plan.json").read_text(encoding="utf-8"))
            self.assertEqual(plan["mode"], "local_compile")
            self.assertFalse(plan["remote_changes_performed"])
            self.assertIn("Microsoft.Web/sites", plan["compiled_resource_counts"])

    def test_generation_merges_existing_gitignore_without_removing_content(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            gitignore = output / ".gitignore"
            original = ".env\nvenv\n__pycache__\nalembic/versions\n"
            gitignore.write_text(original, encoding="utf-8")

            first_manifest = generate_project(
                ProjectConfig(project_name="proyecto-feria"), output
            )
            first_content = gitignore.read_text(encoding="utf-8")
            second_manifest = generate_project(
                ProjectConfig(project_name="proyecto-feria"), output
            )

            self.assertTrue(first_content.startswith(original))
            self.assertIn("venv\n", first_content)
            self.assertIn("*.sops-dec.*\n", first_content)
            self.assertIn(".azure/\n", first_content)
            self.assertEqual(first_content, gitignore.read_text(encoding="utf-8"))
            self.assertEqual(first_manifest, second_manifest)

    def test_sops_config_uses_only_sorted_public_recipients(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            config = ProjectConfig(
                project_name="proyecto-feria",
                sops_age_recipients=(self.RECIPIENT_ONE, self.RECIPIENT_TWO),
            )
            manifest = generate_project(config, output)
            sops_config = (output / ".sops.yaml").read_text(encoding="utf-8")
            self.assertIn(".sops.yaml", manifest["files"])
            self.assertIn(self.RECIPIENT_ONE, sops_config)
            self.assertIn(self.RECIPIENT_TWO, sops_config)
            self.assertNotIn("AGE-" + "SECRET-KEY-", sops_config)

    @unittest.skipUnless(shutil.which("sops"), "SOPS is not installed")
    def test_sops_accepts_generated_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            generate_project(
                ProjectConfig(
                    project_name="proyecto-feria",
                    sops_age_recipients=(self.RECIPIENT_ONE,),
                ),
                output,
            )
            plaintext = output / "secrets.plain.json"
            plaintext.write_text(
                json.dumps({"value": "synthetic-only"}) + "\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    shutil.which("sops") or "sops",
                    "--config",
                    str(output / ".sops.yaml"),
                    "encrypt",
                    "--filename-override",
                    "secrets.enc.json",
                    "--input-type",
                    "json",
                    "--output-type",
                    "json",
                    str(plaintext),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            sanitized_error = completed.stderr.replace(str(output), "<temp>").strip()
            self.assertEqual(
                completed.returncode,
                0,
                f"SOPS rejected generated config: {sanitized_error}",
            )
            self.assertNotIn("synthetic-only", completed.stdout)

    def test_sops_config_is_omitted_without_public_recipients(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            manifest = generate_project(ProjectConfig(project_name="proyecto-feria"), output)
            self.assertNotIn(".sops.yaml", manifest["files"])
            self.assertFalse((output / ".sops.yaml").exists())

    def test_non_interactive_cli_initializes_and_generates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.json"
            output = root / "generated"
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                self.assertEqual(
                    main(
                        [
                            "init",
                            "--non-interactive",
                            "--name",
                            "proyecto-feria",
                            "--expires-on",
                            "2099-12-31",
                            "--sops-age-recipient",
                            self.RECIPIENT_ONE,
                            "--output",
                            str(config_path),
                        ]
                    ),
                    0,
                )
                self.assertEqual(
                    main(
                        [
                            "generate",
                            "--config",
                            str(config_path),
                            "--output",
                            str(output),
                        ]
                    ),
                    0,
                )
            self.assertIn("Configured 1 public SOPS recipient", captured.getvalue())
            manifest = json.loads(
                (output / ".feria/manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["project_name"], "proyecto-feria")
            self.assertEqual(manifest["generator_version"], "0.7.4")
            self.assertIn(
                "examples/azure-workflows/oidc-login-demo.yml", manifest["files"]
            )
            self.assertIn(
                "examples/azure-workflows/azure-lifecycle-demo.yml", manifest["files"]
            )
            self.assertIn(".sops.yaml", manifest["files"])
            self.assertIn("scripts/check_no_plaintext_files.py", manifest["files"])
            generated_gitignore = (output / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("*.sops-dec.*", generated_gitignore)
            generated_precommit = (output / ".pre-commit-config.yaml").read_text(
                encoding="utf-8"
            )
            self.assertIn("forbid-plaintext-secret-files", generated_precommit)
            generated_config = json.loads(
                (output / "feria-project.json").read_text(encoding="utf-8")
            )
            self.assertEqual(generated_config["azure_location"], "brazilsouth")
            self.assertEqual(
                generated_config["compute_profile"], "functions-flex-python"
            )
            self.assertEqual(generated_config["expires_on"], "2099-12-31")
            self.assertEqual(
                generated_config["sops_age_recipients"], [self.RECIPIENT_ONE]
            )
            generated_parameters = (
                output / "infra/bicep/main.bicepparam"
            ).read_text(encoding="utf-8")
            self.assertIn("param projectName = 'proyecto-feria'", generated_parameters)
            self.assertIn("param expiresOn = '2099-12-31'", generated_parameters)

    @unittest.skipUnless(shutil.which("gitleaks"), "Gitleaks is not installed")
    def test_generated_project_is_clean_under_gitleaks(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            generate_project(
                ProjectConfig(
                    project_name="proyecto-feria",
                    sops_age_recipients=(self.RECIPIENT_ONE,),
                ),
                output,
            )
            completed = subprocess.run(
                [
                    shutil.which("gitleaks") or "gitleaks",
                    "dir",
                    str(output),
                    "--config",
                    str(output / ".gitleaks.toml"),
                    "--redact",
                    "--no-banner",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, "Generated baseline was flagged")

    @unittest.skipUnless(shutil.which("az"), "Azure CLI is not installed")
    def test_bicep_template_compiles_to_expected_profile(self):
        completed = subprocess.run(
            [
                shutil.which("az") or "az",
                "bicep",
                "build",
                "--file",
                str(Path("infra/bicep/main.bicep")),
                "--stdout",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        template = json.loads(completed.stdout)
        serialized = json.dumps(template)
        self.assertIn("Microsoft.Web/serverfarms", serialized)
        self.assertIn("Microsoft.Web/sites", serialized)
        self.assertIn("FlexConsumption", serialized)
        self.assertIn('"instanceMemoryMB": 512', serialized)
        self.assertIn('"maximumInstanceCount": 1', serialized)
        self.assertEqual(
            serialized.count('"type": "Microsoft.Authorization/roleAssignments"'),
            2,
        )
        self.assertNotIn("Storage Queue Data Contributor", serialized)
        self.assertNotIn("Storage Blob Data Contributor", serialized)
        self.assertNotIn("Microsoft.Insights/components", serialized)
        self.assertNotIn("Microsoft.DBforMySQL", serialized)

    @unittest.skipUnless(shutil.which("az"), "Azure CLI is not installed")
    def test_local_plan_is_sanitized_and_does_not_call_what_if(self):
        config = ProjectConfig(
            project_name="proyecto-feria",
            expires_on="2099-12-31",
        )
        plan = build_plan(config, Path("infra/bicep/main.bicep"))
        self.assertEqual(plan["mode"], "local_compile")
        self.assertFalse(plan["remote_changes_performed"])
        self.assertFalse(plan["identifiers_retained"])
        self.assertFalse(plan["azure_what_if_succeeded"])
        self.assertNotIn("Microsoft.Resources/resourceGroups", plan["compiled_resource_counts"])
        self.assertIn("Microsoft.Web/sites", plan["compiled_resource_counts"])

    def test_plan_rejects_pending_expiration_before_running_azure_cli(self):
        with patch("framework.starter_kit.planner._run_azure_cli") as run_cli:
            with self.assertRaisesRegex(PlanError, "expires_on must be set"):
                build_plan(
                    ProjectConfig(project_name="proyecto-feria"),
                    Path("infra/bicep/main.bicep"),
                )
            run_cli.assert_not_called()

    def test_what_if_plan_retains_only_change_counts(self):
        compiled = {
            "resources": [
                {"type": "Microsoft.Resources/resourceGroups"},
            ]
        }
        what_if = {
            "changes": [
                {
                    "resourceId": "/subscriptions/private/resourceGroups/private",
                    "changeType": "Create",
                },
                {
                    "resourceId": "/subscriptions/private/resourceGroups/private/x",
                    "changeType": "NoChange",
                },
            ]
        }
        with patch(
            "framework.starter_kit.planner._run_azure_cli",
            side_effect=[json.dumps(compiled), json.dumps(what_if)],
        ):
            plan = build_plan(
                ProjectConfig(
                    project_name="proyecto-feria",
                    expires_on="2099-12-31",
                ),
                Path("infra/bicep/main.bicep"),
                run_what_if=True,
                resource_group="rg-proyecto-feria-dev",
            )
        serialized = json.dumps(plan)
        self.assertEqual(plan["what_if_change_counts"], {"Create": 1, "NoChange": 1})
        self.assertNotIn("subscriptions/private", serialized)
        self.assertFalse(plan["remote_changes_performed"])

    def test_what_if_requires_existing_resource_group_name(self):
        compiled = {"resources": [{"type": "Microsoft.Web/sites"}]}
        with patch(
            "framework.starter_kit.planner._run_azure_cli",
            return_value=json.dumps(compiled),
        ):
            with self.assertRaisesRegex(PlanError, "resource_group is required"):
                build_plan(
                    ProjectConfig(
                        project_name="proyecto-feria",
                        expires_on="2099-12-31",
                    ),
                    Path("infra/bicep/main.bicep"),
                    run_what_if=True,
                )

    def test_apply_rejects_wrong_confirmation_before_azure(self):
        with patch("framework.starter_kit.lifecycle._run_azure_cli") as run_cli:
            with self.assertRaisesRegex(LifecycleError, "Confirmation mismatch"):
                apply_environment(
                    ProjectConfig(
                        project_name="proyecto-feria", expires_on="2099-12-31"
                    ),
                    Path("infra/bicep/main.bicep"),
                    "rg-proyecto-feria-dev",
                    "yes",
                )
            run_cli.assert_not_called()

    def test_apply_retains_only_sanitized_counts(self):
        config = ProjectConfig(
            project_name="proyecto-feria", expires_on="2099-12-31"
        )
        group = self._target_group(config)
        deployment = {
            "id": "/subscriptions/private/deployments/private",
            "properties": {"provisioningState": "Succeeded"},
        }
        resources = [
            {
                "id": "/subscriptions/private/resourceGroups/private/resource",
                "type": "Microsoft.Web/sites",
            }
        ]
        with patch(
            "framework.starter_kit.lifecycle._run_azure_cli",
            side_effect=[json.dumps(group), json.dumps(deployment), json.dumps(resources)],
        ):
            result = apply_environment(
                config,
                Path("infra/bicep/main.bicep"),
                "rg-proyecto-feria-dev",
                "apply:proyecto-feria:dev",
            )
        serialized = json.dumps(result)
        self.assertTrue(result["succeeded"])
        self.assertTrue(result["remote_changes_performed"])
        self.assertNotIn("subscriptions/private", serialized)

    def test_verify_checks_secretless_minimum_profile(self):
        config = ProjectConfig(
            project_name="proyecto-feria", expires_on="2099-12-31"
        )
        resources = [
            {"type": "Microsoft.ManagedIdentity/userAssignedIdentities"},
            {"type": "Microsoft.Storage/storageAccounts"},
            {"type": "Microsoft.Web/serverFarms"},
            {"type": "Microsoft.Web/sites"},
        ]
        storage = [
            {
                "allowBlobPublicAccess": False,
                "allowSharedKeyAccess": False,
                "enableHttpsTrafficOnly": True,
            }
        ]
        function = [
            {
                "id": "/subscriptions/private/function",
                "name": "private-function-name",
                "httpsOnly": True,
            }
        ]
        plans = [{"sku": {"name": "FC1", "tier": "FlexConsumption"}}]
        detail = {
            "properties": {
                "functionAppConfig": {
                    "runtime": {"name": "python", "version": "3.12"},
                    "scaleAndConcurrency": {"maximumInstanceCount": 1},
                }
            }
        }
        settings = [
            {"name": "AzureWebJobsStorage__accountName", "value": "private"},
            {"name": "AzureWebJobsStorage__clientId", "value": "private"},
            {"name": "AzureWebJobsStorage__credential", "value": "managedidentity"},
        ]
        with patch(
            "framework.starter_kit.lifecycle._run_azure_cli",
            side_effect=[
                json.dumps(self._target_group(config)),
                json.dumps(resources),
                json.dumps(storage),
                json.dumps(function),
                json.dumps(plans),
                json.dumps(detail),
                json.dumps(settings),
            ],
        ) as run_cli:
            result = verify_environment(config, "rg-proyecto-feria-dev")
        self.assertTrue(result["succeeded"])
        self.assertTrue(all(result["checks"].values()))
        self.assertNotIn("private", json.dumps(result))
        settings_call = run_cli.call_args_list[-1].args[0]
        self.assertIn("--name", settings_call)
        self.assertIn("--resource-group", settings_call)
        self.assertNotIn("--ids", settings_call)

    def test_destroy_requires_matching_tags_and_confirms_absence(self):
        config = ProjectConfig(
            project_name="proyecto-feria", expires_on="2099-12-31"
        )
        with patch(
            "framework.starter_kit.lifecycle._run_azure_cli",
            side_effect=[json.dumps(self._target_group(config)), "", "false\n"],
        ):
            result = destroy_environment(
                config,
                "rg-proyecto-feria-dev",
                "destroy:proyecto-feria:dev",
            )
        self.assertTrue(result["resource_group_absent"])
        self.assertTrue(result["remote_changes_performed"])

    @staticmethod
    def _target_group(config: ProjectConfig) -> dict[str, object]:
        return {
            "location": config.azure_location,
            "tags": {
                "environment": config.environment,
                "expiresOn": config.expires_on,
                "managedBy": "feria-starter",
                "projectName": config.project_name,
                "purpose": "academic-devsecops-validation",
            },
        }

    @staticmethod
    def _tree_hashes(root: Path) -> dict[str, str]:
        result = {}
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = path.relative_to(root).as_posix()
            result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        return result


if __name__ == "__main__":
    unittest.main()
