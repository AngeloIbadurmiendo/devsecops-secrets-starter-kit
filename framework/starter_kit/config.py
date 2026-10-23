from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PROJECT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{2,30}$")
RESOURCE_GROUP_PATTERN = re.compile(r"^rg-[a-z0-9][a-z0-9-]{2,79}$")
BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
ALLOWED_ENVIRONMENTS = {"dev", "test"}
ALLOWED_AZURE_LOCATIONS = {"brazilsouth"}
ALLOWED_COMPUTE_PROFILES = {"functions-flex-python"}
ALLOWED_DATABASE_PROFILES = {"none"}


class ConfigurationError(ValueError):
    """Raised when a starter-kit configuration is invalid."""


def validate_resource_group_name(value: str) -> str:
    if not RESOURCE_GROUP_PATTERN.fullmatch(value):
        raise ConfigurationError(
            "resource_group must start with rg- and contain only lowercase letters, "
            "digits, or hyphens."
        )
    return value


def _bech32_polymod(values: list[int]) -> int:
    generators = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    checksum = 1
    for value in values:
        top = checksum >> 25
        checksum = ((checksum & 0x1FFFFFF) << 5) ^ value
        for index, generator in enumerate(generators):
            if (top >> index) & 1:
                checksum ^= generator
    return checksum


def is_valid_age_recipient(value: str) -> bool:
    """Validate a native X25519 age recipient, including its Bech32 checksum."""

    if not isinstance(value, str) or len(value) != 62 or not value.startswith("age1"):
        return False
    if value != value.lower():
        return False
    try:
        data = [BECH32_CHARSET.index(character) for character in value[4:]]
    except ValueError:
        return False
    human_readable = [ord(character) >> 5 for character in "age"]
    human_readable += [0]
    human_readable += [ord(character) & 31 for character in "age"]
    return _bech32_polymod(human_readable + data) == 1


@dataclass(frozen=True)
class ProjectConfig:
    project_name: str
    environment: str = "dev"
    azure_location: str = "brazilsouth"
    compute_profile: str = "functions-flex-python"
    database_profile: str = "none"
    expires_on: str = "pending"
    secret_scanning: bool = True
    sops: bool = True
    github_azure_oidc: bool = True
    sops_age_recipients: tuple[str, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        if isinstance(self.sops_age_recipients, list):
            object.__setattr__(
                self, "sops_age_recipients", tuple(self.sops_age_recipients)
            )

    def validate(self) -> None:
        if self.schema_version != 1:
            raise ConfigurationError("Unsupported schema_version; expected 1.")
        if not PROJECT_NAME_PATTERN.fullmatch(self.project_name):
            raise ConfigurationError(
                "project_name must use 3-31 lowercase letters, digits, or hyphens "
                "and start with a letter."
            )
        if self.environment not in ALLOWED_ENVIRONMENTS:
            raise ConfigurationError("environment must be dev or test.")
        if self.azure_location not in ALLOWED_AZURE_LOCATIONS:
            raise ConfigurationError(
                "azure_location is not validated; only brazilsouth is supported."
            )
        if self.compute_profile not in ALLOWED_COMPUTE_PROFILES:
            raise ConfigurationError(
                "compute_profile is not validated; only functions-flex-python is supported."
            )
        if self.database_profile not in ALLOWED_DATABASE_PROFILES:
            raise ConfigurationError(
                "database_profile is not validated; only none is currently supported."
            )
        if not all((self.secret_scanning, self.sops, self.github_azure_oidc)):
            raise ConfigurationError("Core security controls cannot be disabled.")
        if not isinstance(self.sops_age_recipients, tuple):
            raise ConfigurationError("sops_age_recipients must be a list of public recipients.")
        if len(self.sops_age_recipients) > 8:
            raise ConfigurationError("At most eight SOPS age recipients are supported.")
        if len(set(self.sops_age_recipients)) != len(self.sops_age_recipients):
            raise ConfigurationError("SOPS age recipients must be unique.")
        if any(not is_valid_age_recipient(item) for item in self.sops_age_recipients):
            raise ConfigurationError("A SOPS age recipient is invalid.")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ProjectConfig":
        expected = set(cls.__dataclass_fields__)
        unknown = set(raw) - expected
        if unknown:
            raise ConfigurationError(
                f"Unknown configuration fields: {', '.join(sorted(unknown))}."
            )
        try:
            config = cls(**raw)
        except TypeError as exc:
            raise ConfigurationError(f"Invalid configuration structure: {exc}") from exc
        config.validate()
        return config


def read_config(path: Path) -> ProjectConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Cannot read configuration: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError("Configuration root must be an object.")
    return ProjectConfig.from_dict(raw)


def write_config(path: Path, config: ProjectConfig, *, overwrite: bool = False) -> None:
    config.validate()
    content = json.dumps(config.to_dict(), indent=2, sort_keys=True) + "\n"
    if path.exists() and not overwrite:
        if path.read_text(encoding="utf-8") == content:
            return
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
