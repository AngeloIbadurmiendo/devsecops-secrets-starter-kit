from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from .config import ConfigurationError, ProjectConfig, validate_resource_group_name
from .planner import _validated_expiry


EXPECTED_MANAGED_BY = "feria-starter"
EXPECTED_PURPOSE = "academic-devsecops-validation"


class LifecycleError(RuntimeError):
    """Raised when an Azure lifecycle operation cannot be completed safely."""


def _run_azure_cli(arguments: list[str], *, stage: str) -> str:
    executable = shutil.which("az")
    if not executable:
        raise LifecycleError("Azure CLI is required for lifecycle operations.")
    completed = subprocess.run(
        [executable, *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise LifecycleError(
            f"Azure CLI failed during {stage}; raw output was not retained because "
            "it can contain account identifiers."
        )
    return completed.stdout


def _run_json(arguments: list[str], *, stage: str) -> Any:
    raw = _run_azure_cli([*arguments, "--only-show-errors", "--output", "json"], stage=stage)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LifecycleError(f"Azure returned invalid JSON during {stage}.") from exc


def _validate_resource_group_name(resource_group: str) -> str:
    try:
        return validate_resource_group_name(resource_group)
    except ConfigurationError as exc:
        raise LifecycleError(str(exc)) from exc


def _expected_confirmation(operation: str, config: ProjectConfig) -> str:
    return f"{operation}:{config.project_name}:{config.environment}"


def _require_confirmation(
    operation: str, config: ProjectConfig, confirmation: str
) -> None:
    expected = _expected_confirmation(operation, config)
    if confirmation != expected:
        raise LifecycleError(
            f"Confirmation mismatch; expected the exact value '{expected}'."
        )


def _validate_target_group(
    config: ProjectConfig, resource_group: str
) -> dict[str, Any]:
    _validate_resource_group_name(resource_group)
    expires_on = _validated_expiry(config.expires_on)
    raw = _run_json(
        ["group", "show", "--name", resource_group],
        stage="target resource-group validation",
    )
    if not isinstance(raw, dict):
        raise LifecycleError("Azure returned an unexpected resource-group response.")
    tags = raw.get("tags")
    if not isinstance(tags, dict):
        raise LifecycleError("Target resource group is missing required lifecycle tags.")
    expected_tags = {
        "environment": config.environment,
        "expiresOn": expires_on,
        "managedBy": EXPECTED_MANAGED_BY,
        "projectName": config.project_name,
        "purpose": EXPECTED_PURPOSE,
    }
    mismatches = [
        key for key, expected in expected_tags.items() if tags.get(key) != expected
    ]
    if raw.get("location") != config.azure_location:
        mismatches.append("location")
    if mismatches:
        raise LifecycleError(
            "Target resource group does not match the declared project: "
            + ", ".join(sorted(mismatches))
            + "."
        )
    return raw


def _resource_counts(resource_group: str) -> dict[str, int]:
    resources = _run_json(
        ["resource", "list", "--resource-group", resource_group],
        stage="resource inventory",
    )
    if not isinstance(resources, list):
        raise LifecycleError("Azure returned an unexpected resource inventory.")
    counts: Counter[str] = Counter()
    for resource in resources:
        if isinstance(resource, dict) and isinstance(resource.get("type"), str):
            counts[resource["type"]] += 1
    return dict(sorted(counts.items()))


def apply_environment(
    config: ProjectConfig,
    template_path: Path,
    resource_group: str,
    confirmation: str,
) -> dict[str, object]:
    config.validate()
    expires_on = _validated_expiry(config.expires_on)
    _require_confirmation("apply", config, confirmation)
    _validate_target_group(config, resource_group)
    if not template_path.is_file():
        raise LifecycleError("Bicep template was not found in the generated project.")

    deployment = _run_json(
        [
            "deployment",
            "group",
            "create",
            "--name",
            f"feria-apply-{config.project_name}-{config.environment}",
            "--resource-group",
            resource_group,
            "--template-file",
            str(template_path),
            "--parameters",
            f"projectName={config.project_name}",
            f"environment={config.environment}",
            f"location={config.azure_location}",
            f"expiresOn={expires_on}",
        ],
        stage="Azure resource-group deployment",
    )
    state = (
        deployment.get("properties", {}).get("provisioningState")
        if isinstance(deployment, dict)
        else None
    )
    if state != "Succeeded":
        raise LifecycleError("Azure deployment did not report Succeeded.")
    return {
        "schema_version": 1,
        "operation": "apply",
        "succeeded": True,
        "deployment_provisioning_state": "Succeeded",
        "resource_counts": _resource_counts(resource_group),
        "remote_changes_performed": True,
        "identifiers_retained": False,
    }


def verify_environment(
    config: ProjectConfig, resource_group: str
) -> dict[str, object]:
    config.validate()
    _validate_target_group(config, resource_group)
    counts = _resource_counts(resource_group)

    storage_accounts = _run_json(
        ["storage", "account", "list", "--resource-group", resource_group],
        stage="storage verification",
    )
    function_apps = _run_json(
        ["functionapp", "list", "--resource-group", resource_group],
        stage="function-app verification",
    )
    plans = _run_json(
        ["functionapp", "plan", "list", "--resource-group", resource_group],
        stage="hosting-plan verification",
    )
    if not all(isinstance(item, list) for item in (storage_accounts, function_apps, plans)):
        raise LifecycleError("Azure returned an unexpected verification response.")
    if len(storage_accounts) != 1 or len(function_apps) != 1 or len(plans) != 1:
        raise LifecycleError("Expected exactly one Storage account, Function App, and plan.")

    storage = storage_accounts[0]
    function = function_apps[0]
    plan = plans[0]
    function_id = function.get("id")
    function_name = function.get("name")
    if not isinstance(function_id, str):
        raise LifecycleError("Function App did not expose a resource ID for verification.")
    if not isinstance(function_name, str):
        raise LifecycleError("Function App did not expose a name for verification.")
    function_detail = _run_json(
        [
            "resource",
            "show",
            "--ids",
            function_id,
            "--api-version",
            "2024-04-01",
        ],
        stage="Function App configuration verification",
    )
    app_settings = _run_json(
        [
            "functionapp",
            "config",
            "appsettings",
            "list",
            "--name",
            function_name,
            "--resource-group",
            resource_group,
        ],
        stage="Function App secretless-settings verification",
    )
    if not isinstance(function_detail, dict) or not isinstance(app_settings, list):
        raise LifecycleError("Azure returned an unexpected Function App response.")

    setting_names = {
        item.get("name") for item in app_settings if isinstance(item, dict)
    }
    required_settings = {
        "AzureWebJobsStorage__accountName",
        "AzureWebJobsStorage__clientId",
        "AzureWebJobsStorage__credential",
    }
    properties = function_detail.get("properties", {})
    function_config = properties.get("functionAppConfig", {})
    runtime = function_config.get("runtime", {})
    scale = function_config.get("scaleAndConcurrency", {})
    sku = plan.get("sku", {}) if isinstance(plan, dict) else {}
    normalized_resource_types = {item.lower() for item in counts}

    checks = {
        "database_resources_absent": not any(
            "dbformysql" in resource_type for resource_type in normalized_resource_types
        ),
        "function_https_only": function.get("httpsOnly") is True,
        "function_runtime_python_312": runtime.get("name") == "python"
        and runtime.get("version") == "3.12",
        "maximum_instance_count_one": scale.get("maximumInstanceCount") == 1,
        "plan_is_flex_consumption": sku.get("tier") == "FlexConsumption"
        and sku.get("name") == "FC1",
        "secretless_storage_settings": required_settings.issubset(setting_names)
        and "AzureWebJobsStorage" not in setting_names,
        "storage_blob_public_access_disabled": storage.get("allowBlobPublicAccess")
        is False,
        "storage_https_only": storage.get("enableHttpsTrafficOnly") is True,
        "storage_shared_key_access_disabled": storage.get("allowSharedKeyAccess")
        is False,
        "telemetry_resources_absent": not any(
            resource_type.startswith("microsoft.insights/")
            or resource_type.startswith("microsoft.operationalinsights/")
            for resource_type in normalized_resource_types
        ),
    }
    required_types = {
        "microsoft.managedidentity/userassignedidentities",
        "microsoft.storage/storageaccounts",
        "microsoft.web/serverfarms",
        "microsoft.web/sites",
    }
    checks["required_resource_types_present"] = required_types.issubset(
        normalized_resource_types
    )
    succeeded = all(checks.values())
    if not succeeded:
        failed = ", ".join(sorted(name for name, value in checks.items() if not value))
        raise LifecycleError(f"Azure verification failed: {failed}.")
    return {
        "schema_version": 1,
        "operation": "verify",
        "succeeded": True,
        "checks": checks,
        "resource_counts": counts,
        "remote_changes_performed": False,
        "identifiers_retained": False,
    }


def destroy_environment(
    config: ProjectConfig, resource_group: str, confirmation: str
) -> dict[str, object]:
    config.validate()
    _require_confirmation("destroy", config, confirmation)
    _validate_target_group(config, resource_group)
    _run_azure_cli(
        [
            "group",
            "delete",
            "--name",
            resource_group,
            "--yes",
            "--only-show-errors",
        ],
        stage="resource-group destruction",
    )
    exists = _run_azure_cli(
        ["group", "exists", "--name", resource_group, "--output", "tsv"],
        stage="post-destruction verification",
    ).strip()
    if exists.lower() != "false":
        raise LifecycleError("Azure still reports the target resource group after deletion.")
    return {
        "schema_version": 1,
        "operation": "destroy",
        "succeeded": True,
        "resource_group_absent": True,
        "remote_changes_performed": True,
        "identifiers_retained": False,
    }


def write_lifecycle_result(path: Path, result: dict[str, object]) -> None:
    content = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise LifecycleError(f"Refusing to overwrite an existing different result: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
