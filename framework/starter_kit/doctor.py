from __future__ import annotations

import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ToolCheck:
    name: str
    required: bool
    available: bool


def inspect_tools(mode: str) -> list[ToolCheck]:
    if mode not in {"local", "cloud"}:
        raise ValueError("mode must be local or cloud")

    requirements = {
        "python": True,
        "git": True,
        "gh": mode == "cloud",
        "az": mode == "cloud",
        "azd": mode == "cloud",
        "sops": mode == "cloud",
        "age": mode == "cloud",
    }
    checks: list[ToolCheck] = []
    for name, required in requirements.items():
        available = bool(sys.executable) if name == "python" else shutil.which(name) is not None
        checks.append(ToolCheck(name=name, required=required, available=available))
    bicep_names = ("bicep.exe", "bicep") if sys.platform == "win32" else ("bicep",)
    azure_bicep = any((Path.home() / ".azure" / "bin" / name).is_file() for name in bicep_names)
    bicep_available = shutil.which("bicep") is not None or azure_bicep
    checks.append(
        ToolCheck(name="bicep", required=mode == "cloud", available=bicep_available)
    )
    return checks


def doctor_report(mode: str) -> dict[str, object]:
    checks = inspect_tools(mode)
    blockers = [check.name for check in checks if check.required and not check.available]
    return {
        "schema_version": 1,
        "mode": mode,
        "ready": not blockers,
        "blockers": blockers,
        "tools": [asdict(check) for check in checks],
        "remote_changes_performed": False,
    }
