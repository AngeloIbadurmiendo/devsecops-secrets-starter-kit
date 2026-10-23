"""Read bounded Azure diagnostics; retain allowlisted facts, never raw logs."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess


SIGNALS = {
    "authorization_error": r"AuthorizationPermissionMismatch|AuthorizationFailure|forbidden|access denied",
    "missing_python_module": r"ModuleNotFoundError|No module named",
    "python_import_error": r"ImportError|cannot import name",
    "host_startup_error": r"host (?:startup|initialization).*fail|failed to start.*host",
    "storage_connection_error": r"unable to (?:connect|access).*storage|failed.*AzureWebJobsStorage",
    "timeout": r"timed out|timeout",
    "remote_build_error": r"build failed|failed to build|Oryx.*error",
    "remote_build_success": r"build successful|successfully built|Oryx.*succeeded",
    "service_unavailable": r"service unavailable|\b503\b",
    "invalid_consecutive_route_separator": r"route template separator character.*cannot appear consecutively",
}


def signal_categories(text):
    return sorted(name for name, pattern in SIGNALS.items()
                  if re.search(pattern, text, re.IGNORECASE))


def query(*args):
    try:
        result = subprocess.run([shutil.which("az") or "az", *args,
                                 "--only-show-errors", "-o", "json"],
                                capture_output=True, text=True, timeout=25)
    except (OSError, subprocess.TimeoutExpired):
        return None, {"query_passed": False, "categories": ["cli_or_query_timeout"]}
    metadata = {"query_passed": result.returncode == 0,
                "categories": (signal_categories(result.stdout + result.stderr)
                               if result.returncode else [])}
    try:
        data = json.loads(result.stdout)
    except ValueError:
        metadata["json_received"] = False
        return None, metadata
    metadata["json_received"] = True
    return data, metadata


def required(*args):
    data, metadata = query(*args)
    if not metadata["query_passed"] or data is None:
        raise ValueError("required target query failed; raw diagnostics suppressed")
    return data


def collect(config, group_name):
    if datetime.fromisoformat(config["expires_on"]).date() <= datetime.now(timezone.utc).date():
        raise ValueError("experimental configuration expired")
    account = required("account", "show")
    subscription = required("rest", "--method", "get", "--url",
                            "https://management.azure.com/subscriptions/" + account["id"]
                            + "?api-version=2020-01-01")
    policies = subscription.get("subscriptionPolicies", {})
    if (subscription.get("state") != "Enabled"
            or policies.get("quotaId") != "AzureForStudents_2018-01-01"
            or policies.get("spendingLimit") != "On"):
        raise ValueError("student spending guard failed")
    group = required("group", "show", "--name", group_name)
    tags = {"projectName": config["project_name"], "environment": config["environment"],
            "expiresOn": config["expires_on"], "managedBy": "feria-starter",
            "purpose": "academic-devsecops-validation"}
    if (group.get("location") != config["azure_location"]
            or any(group.get("tags", {}).get(k) != v for k, v in tags.items())):
        raise ValueError("target ownership guard failed")
    apps = required("functionapp", "list", "--resource-group", group_name)
    if len(apps) != 1:
        raise ValueError("expected one experimental Function")
    app = apps[0]
    detail = required("resource", "show", "--ids", app["id"], "--api-version", "2024-04-01")
    fc = detail["properties"]["functionAppConfig"]
    scale = fc["scaleAndConcurrency"]
    if (fc["runtime"] != {"name": "python", "version": "3.12"}
            or scale.get("maximumInstanceCount") != 1
            or scale.get("instanceMemoryMB") != 512 or scale.get("alwaysReady")
            or not detail["properties"].get("httpsOnly")):
        raise ValueError("runtime spending guard failed")
    report = {"schema_version": 1, "observed_at_utc": datetime.now(timezone.utc).isoformat(),
              "identifiers_retained": False, "raw_logs_retained": False,
              "cloud_changes_performed": False, "target_guard_passed": True, "queries": {}}
    resources, metadata = query("resource", "list", "--resource-group", group_name)
    report["queries"]["resource_inventory"] = metadata
    if isinstance(resources, list):
        storage = [item for item in resources
                   if item.get("type", "").lower() == "microsoft.storage/storageaccounts"]
        principals = {value.get("principalId") for value in
                      detail.get("identity", {}).get("userAssignedIdentities", {}).values()}
        if len(storage) == 1:
            assignments, metadata = query("role", "assignment", "list", "--scope",
                                           storage[0]["id"], "--include-inherited")
            report["queries"]["storage_role_assignments"] = metadata
            if isinstance(assignments, list):
                definitions = {item.get("roleDefinitionId", "").split("/")[-1].lower()
                               for item in assignments if item.get("principalId") in principals}
                report["host_storage_roles"] = {
                    "blob_owner_assignment_present": "b7e6dc6d-f1e8-4753-8033-0f276bb0955b" in definitions,
                    "table_contributor_assignment_present": "0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3" in definitions,
                    "effective_data_access_verified": False,
                }
    base = ("--name", app["name"], "--resource-group", group_name)
    settings, metadata = query("functionapp", "config", "appsettings", "list", *base)
    report["queries"]["settings"] = metadata
    if isinstance(settings, list):
        values = {entry["name"]: entry.get("value") for entry in settings}
        report["settings"] = {
            "extension_version_present": "FUNCTIONS_EXTENSION_VERSION" in values,
            "extension_version_major_4": values.get("FUNCTIONS_EXTENSION_VERSION") == "~4",
            "legacy_worker_runtime_present": "FUNCTIONS_WORKER_RUNTIME" in values,
            "storage_credential_managedidentity": values.get("AzureWebJobsStorage__credential") == "managedidentity",
            "storage_account_name_present": bool(values.get("AzureWebJobsStorage__accountName")),
            "storage_client_id_present": bool(values.get("AzureWebJobsStorage__clientId")),
            "storage_connection_string_present": bool(values.get("AzureWebJobsStorage")),
        }
    for name, args in (
        ("functions", ("functionapp", "function", "list", *base)),
        ("deployment_list", ("functionapp", "log", "deployment", "list", *base)),
        ("deployment_logs", ("functionapp", "log", "deployment", "show", *base)),
        ("host_status", ("rest", "--method", "get", "--url",
                         "https://management.azure.com" + app["id"]
                         + "/hostruntime/admin/host/status?api-version=2024-04-01")),
        ("detectors", ("rest", "--method", "get", "--url",
                       "https://management.azure.com" + app["id"] + "/detectors?api-version=2024-04-01")),
    ):
        data, metadata = query(*args)
        if name == "deployment_logs" and data is not None:
            metadata["categories"] = signal_categories(json.dumps(data))
        report["queries"][name] = metadata
        if name == "functions" and isinstance(data, list):
            report["indexed_function_count"] = len(data)
        if name == "host_status" and isinstance(data, dict):
            state = str(data.get("state", "")).lower()
            report["host_running"] = state == "running"
            report["host_state"] = state if state in {
                "running", "default", "starting", "stopped", "error", "offline", "initializing"
            } else "unknown"
            report["host_version_major_4"] = str(data.get("version", "")).startswith("4.")
            errors = data.get("errors", [])
            report["host_error_categories"] = signal_categories(json.dumps(errors))
            report["host_error_count"] = len(errors) if isinstance(errors, list) else None
        if name == "detectors" and isinstance(data, dict):
            report["detector_count"] = len(data.get("value", []))
            selected = [item["name"] for item in data.get("value", [])
                        if re.fullmatch(r"[A-Za-z0-9_-]+", item.get("name", ""))
                        and re.search(r"flex.*deploy|functionappdown", item["name"], re.I)][:2]
            for index, detector in enumerate(selected, 1):
                _, detector_meta = query("rest", "--method", "get", "--url",
                                         "https://management.azure.com" + app["id"]
                                         + "/detectors/" + detector + "?api-version=2024-04-01")
                report["queries"]["selected_detector_" + str(index)] = detector_meta
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or not args.output.parent.is_dir():
        raise SystemExit("output must be new in an existing directory")
    try:
        report = collect(json.loads(args.config.read_text(encoding="utf-8")), args.resource_group)
    except (ValueError, KeyError, TypeError) as exception:
        raise SystemExit("diagnostic guard/query failed; details suppressed") from exception
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    print("Allowlisted diagnostic report saved; no raw logs or identifiers retained")


if __name__ == "__main__":
    main()
