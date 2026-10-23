from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .config import ConfigurationError, ProjectConfig, validate_resource_group_name


class PlanError(RuntimeError):
    """Raised when a read-only deployment plan cannot be produced safely."""


def _validated_expiry(value: str, *, today: date | None = None) -> str:
    if value == "pending":
        raise PlanError("expires_on must be set before plan; 'pending' is not deployable.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise PlanError("expires_on must use YYYY-MM-DD format.") from exc
    current = today or datetime.now(timezone.utc).date()
    if parsed <= current:
        raise PlanError("expires_on must be later than the current UTC date.")
    return parsed.isoformat()


def _run_azure_cli(arguments: list[str], *, stage: str) -> str:
    executable = shutil.which("az")
    if not executable:
        raise PlanError("Azure CLI is required to build or inspect the Bicep plan.")
    completed = subprocess.run(
        [executable, *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise PlanError(
            f"Azure CLI failed during {stage}; raw output was not retained because "
            "it can contain account identifiers."
        )
    return completed.stdout


def _collect_resource_types(template: dict[str, Any]) -> Counter[str]:
    result: Counter[str] = Counter()

    def visit(resources: object) -> None:
        if not isinstance(resources, list):
            return
        for resource in resources:
            if not isinstance(resource, dict):
                continue
            resource_type = resource.get("type")
            if isinstance(resource_type, str):
                result[resource_type] += 1
            visit(resource.get("resources"))
            properties = resource.get("properties")
            if isinstance(properties, dict):
                nested_template = properties.get("template")
                if isinstance(nested_template, dict):
                    visit(nested_template.get("resources"))

    visit(template.get("resources"))
    return result


def _compiled_template(template_path: Path) -> dict[str, Any]:
    if not template_path.is_file():
        raise PlanError("Bicep template was not found in the generated project.")
    raw = _run_azure_cli(
        ["bicep", "build", "--file", str(template_path), "--stdout"],
        stage="local Bicep compilation",
    )
    try:
        template = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PlanError("Bicep compilation did not return a valid JSON template.") from exc
    if not isinstance(template, dict):
        raise PlanError("Bicep compilation returned an unexpected template structure.")
    return template


def _what_if_summary(
    config: ProjectConfig,
    template_path: Path,
    expires_on: str,
    resource_group: str,
) -> dict[str, int]:
    try:
        validate_resource_group_name(resource_group)
    except ConfigurationError as exc:
        raise PlanError(str(exc)) from exc
    raw = _run_azure_cli(
        [
            "deployment",
            "group",
            "what-if",
            "--name",
            f"feria-plan-{config.project_name}-{config.environment}",
            "--resource-group",
            resource_group,
            "--template-file",
            str(template_path),
            "--parameters",
            f"projectName={config.project_name}",
            f"environment={config.environment}",
            f"location={config.azure_location}",
            f"expiresOn={expires_on}",
            "--result-format",
            "ResourceIdOnly",
            "--no-pretty-print",
            "--only-show-errors",
            "--output",
            "json",
        ],
        stage="Azure Resource Manager what-if",
    )
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PlanError("Azure what-if did not return valid JSON.") from exc
    changes = result.get("changes", []) if isinstance(result, dict) else []
    if not isinstance(changes, list):
        raise PlanError("Azure what-if returned an unexpected result structure.")
    counts: Counter[str] = Counter()
    for change in changes:
        if not isinstance(change, dict):
            continue
        change_type = change.get("changeType")
        counts[str(change_type) if change_type else "Unknown"] += 1
    return dict(sorted(counts.items()))


def build_plan(
    config: ProjectConfig,
    template_path: Path,
    *,
    run_what_if: bool = False,
    resource_group: str | None = None,
) -> dict[str, object]:
    config.validate()
    expires_on = _validated_expiry(config.expires_on)
    template = _compiled_template(template_path)
    resource_counts = _collect_resource_types(template)
    if not resource_counts:
        raise PlanError("Compiled template contains no resources to review.")

    plan: dict[str, object] = {
        "schema_version": 1,
        "mode": "azure_what_if" if run_what_if else "local_compile",
        "profile": {
            "azure_location": config.azure_location,
            "compute_profile": config.compute_profile,
            "database_profile": config.database_profile,
            "environment": config.environment,
            "expires_on": expires_on,
            "project_name": config.project_name,
        },
        "compiled_resource_counts": dict(sorted(resource_counts.items())),
        "local_bicep_validation_succeeded": True,
        "remote_changes_performed": False,
        "identifiers_retained": False,
    }
    if run_what_if:
        if not resource_group:
            raise PlanError("resource_group is required for Azure what-if.")
        plan["what_if_change_counts"] = _what_if_summary(
            config, template_path, expires_on, resource_group
        )
        plan["azure_what_if_succeeded"] = True
    else:
        plan["azure_what_if_succeeded"] = False
    return plan


def write_plan(path: Path, plan: dict[str, object]) -> None:
    content = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise PlanError(f"Refusing to overwrite an existing different plan: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
