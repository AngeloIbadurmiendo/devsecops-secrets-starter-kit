from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import __version__
from .config import ProjectConfig
from .scaffold import application_files


class GenerationConflictError(RuntimeError):
    """Raised when generation would overwrite user-owned content."""


SOURCE_ROOT = Path(__file__).resolve().parents[2]


def _demo_source(name: str) -> Path:
    """Use active examples in the source checkout and inert copies after generation."""

    source_workflow = SOURCE_ROOT / ".github/workflows" / name
    if source_workflow.is_file():
        return source_workflow
    return SOURCE_ROOT / "examples/azure-workflows" / name


COPIED_ASSETS = {
    ".gitleaks.toml": SOURCE_ROOT / ".gitleaks.toml",
    ".pre-commit-config.yaml": SOURCE_ROOT / ".pre-commit-config.yaml",
    ".github/workflows/reusable-secret-scan.yml": (
        SOURCE_ROOT / ".github/workflows/reusable-secret-scan.yml"
    ),
    ".github/workflows/secret-scan.yml": (
        SOURCE_ROOT / ".github/workflows/secret-scan.yml"
    ),
    "examples/azure-workflows/oidc-login-demo.yml": (
        _demo_source("oidc-login-demo.yml")
    ),
    "examples/azure-workflows/azure-lifecycle-demo.yml": (
        _demo_source("azure-lifecycle-demo.yml")
    ),
    "scripts/check_no_plaintext_files.py": SOURCE_ROOT
    / "scripts/check_no_plaintext_files.py",
    "infra/bicep/main.bicep": SOURCE_ROOT / "infra/bicep/main.bicep",
    "infra/bicep/modules/functions-flex-python.bicep": (
        SOURCE_ROOT / "infra/bicep/modules/functions-flex-python.bicep"
    ),
}

# Keep generated workflows self-contained, without fetching a private repository.
RUNTIME_FILES = (
    "framework/__init__.py",
    "framework/starter_kit/__init__.py",
    "framework/starter_kit/__main__.py",
    "framework/starter_kit/cli.py",
    "framework/starter_kit/config.py",
    "framework/starter_kit/doctor.py",
    "framework/starter_kit/generator.py",
    "framework/starter_kit/lifecycle.py",
    "framework/starter_kit/planner.py",
    "framework/starter_kit/scaffold.py",
)
COPIED_ASSETS.update({name: SOURCE_ROOT / name for name in RUNTIME_FILES})

GITIGNORE_REQUIRED_LINES = (
    ".env",
    ".env.*",
    "!.env.example",
    "*.decrypted.*",
    "*.sops-dec.*",
    "secrets.plain.*",
    ".sops-age-keys/",
    ".azure/",
    "local.settings.json",
    ".venv/",
    "__pycache__/",
    "*.pyc",
)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _merge_gitignore(existing: bytes) -> bytes:
    try:
        text = existing.decode("utf-8")
    except UnicodeDecodeError as error:
        raise GenerationConflictError(
            "Refusing to merge non-UTF-8 file: .gitignore"
        ) from error

    present = {line.strip() for line in text.splitlines()}
    missing = [line for line in GITIGNORE_REQUIRED_LINES if line not in present]
    if not missing:
        return existing

    separator = "" if not text or text.endswith(("\n", "\r")) else "\n"
    block = (
        "\n# Managed security exclusions added by feria-starter.\n"
        + "\n".join(missing)
        + "\n"
    )
    return (text + separator + block).encode("utf-8")


def _sops_config(recipients: tuple[str, ...]) -> bytes:
    rendered_recipients = ",\n      ".join(sorted(recipients))
    return (
        "# Public recipients only. Never place private age key material here.\n"
        "creation_rules:\n"
        "  - path_regex: '(^|.*[\\\\/])secrets\\.enc\\.(yaml|yml|json)$'\n"
        "    age: >-\n"
        f"      {rendered_recipients}\n"
    ).encode("utf-8")


def _bicep_parameters(config: ProjectConfig) -> bytes:
    def quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    return (
        "using './main.bicep'\n\n"
        f"param projectName = {quote(config.project_name)}\n"
        f"param environment = {quote(config.environment)}\n"
        f"param location = {quote(config.azure_location)}\n"
        f"param expiresOn = {quote(config.expires_on)}\n"
    ).encode("utf-8")


def _generated_precommit(content: bytes) -> bytes:
    marker = b"id: forbid-functions-local-settings"
    if marker in content:
        return content
    return content + (
        "\n  - repo: local\n"
        "    hooks:\n"
        "      - id: forbid-functions-local-settings\n"
        "        name: Forbid Azure Functions local settings\n"
        "        entry: python scripts/check_local_settings.py\n"
        "        language: system\n"
        "        types: [file]\n"
    ).encode("utf-8")


def desired_files(config: ProjectConfig) -> dict[str, bytes]:
    config.validate()
    files = {
        target: source.read_bytes() for target, source in COPIED_ASSETS.items()
    }
    files["feria-project.json"] = _json_bytes(config.to_dict())
    files["infra/bicep/main.bicepparam"] = _bicep_parameters(config)
    files[".env.example"] = (
        "# Non-secret configuration only. Never commit .env files.\n"
        "APP_ENV=dev\n"
    ).encode("utf-8")
    files[".pre-commit-config.yaml"] = _generated_precommit(
        files[".pre-commit-config.yaml"]
    )
    files.update(application_files(config))
    files[".gitignore"] = ("\n".join(GITIGNORE_REQUIRED_LINES) + "\n").encode(
        "utf-8"
    )
    files["SECURITY.md"] = (
        "# Security baseline\n\n"
        "- Install hooks with `pre-commit install`.\n"
        "- Store no real credentials in Git, including revoked values.\n"
        "- Configure SOPS only with public age recipients; private keys stay outside Git.\n"
        "- Use GitHub-Azure OIDC; do not create a permanent client secret.\n"
        "- Treat scanner output as sensitive and retain only redacted evidence.\n"
    ).encode("utf-8")
    if config.sops_age_recipients:
        files[".sops.yaml"] = _sops_config(config.sops_age_recipients)
    return files


def generate_project(config: ProjectConfig, output: Path) -> dict[str, object]:
    files = desired_files(config)
    gitignore_path = output / ".gitignore"
    if gitignore_path.exists():
        files[".gitignore"] = _merge_gitignore(gitignore_path.read_bytes())

    conflicts = []
    for relative_path, content in files.items():
        destination = output / relative_path
        if (
            relative_path != ".gitignore"
            and destination.exists()
            and destination.read_bytes() != content
        ):
            conflicts.append(relative_path)
    if conflicts:
        raise GenerationConflictError(
            "Refusing to overwrite modified files: " + ", ".join(sorted(conflicts))
        )

    manifest = {
        "schema_version": 1,
        "generator_version": __version__,
        "project_name": config.project_name,
        "remote_changes_performed": False,
        "files": {
            name: _sha256(content) for name, content in sorted(files.items())
        },
    }
    manifest_path = output / ".feria/manifest.json"
    manifest_content = _json_bytes(manifest)
    if manifest_path.exists() and manifest_path.read_bytes() != manifest_content:
        raise GenerationConflictError(
            "Refusing to overwrite modified file: .feria/manifest.json"
        )
    for relative_path, content in files.items():
        destination = output / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(manifest_content)
    return manifest
