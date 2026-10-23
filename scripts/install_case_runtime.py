"""Install only the generated runtime alongside an unchanged legacy baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


RUNTIME_FILES = (
    "framework/__init__.py", "framework/starter_kit/__init__.py",
    "framework/starter_kit/__main__.py", "framework/starter_kit/cli.py",
    "framework/starter_kit/config.py", "framework/starter_kit/doctor.py",
    "framework/starter_kit/generator.py", "framework/starter_kit/lifecycle.py",
    "framework/starter_kit/planner.py",
)


def install_runtime(source: Path, target: Path, source_commit: str) -> dict:
    source, target = source.resolve(), target.resolve()
    if source == target or source in target.parents or target in source.parents:
        raise ValueError("Source and target must be separate checkouts.")
    baseline_path = target / ".feria/manifest.json"
    baseline = baseline_path.read_bytes()
    if json.loads(baseline)["generator_version"] != "0.7.2":
        raise ValueError("This additive migration supports baseline 0.7.2 only.")
    contents = {name: (source / name).read_bytes().replace(b"\r\n", b"\n")
                for name in RUNTIME_FILES}
    manifest = {
        "schema_version": 1, "mode": "additive_runtime_only",
        "source_commit": source_commit, "runtime_version": "0.7.3",
        "legacy_baseline_sha256": hashlib.sha256(baseline).hexdigest(),
        "legacy_baseline_modified": False, "remote_changes_performed": False,
        "files": {name: hashlib.sha256(data).hexdigest()
                  for name, data in sorted(contents.items())},
    }
    contents[".feria/runtime-manifest.json"] = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode()
    # Preflight the complete set; never replace a project's existing package.
    for name, data in contents.items():
        path = target / name
        if path.exists() and path.read_bytes().replace(b"\r\n", b"\n") != data:
            raise ValueError("Runtime migration conflicts with existing content.")
        if any(parent.exists() and not parent.is_dir()
               for parent in path.parents if parent != target.parent):
            raise ValueError("Runtime migration parent is not a directory.")
    for name, data in contents.items():
        path = target / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    if baseline_path.read_bytes() != baseline:
        raise RuntimeError("Legacy baseline unexpectedly changed.")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    # Execution is explicit. Inspect only metadata, never source application files.
    revisions = []
    for root in (args.source, args.target):
        state = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                               capture_output=True, check=True)
        if state.stdout.strip():
            raise ValueError("Both checkouts must be clean before migration.")
        revisions.append(subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip())
    install_runtime(args.source, args.target, revisions[0])
    print("Installed nine runtime modules; legacy baseline unchanged; no Cloud calls.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
