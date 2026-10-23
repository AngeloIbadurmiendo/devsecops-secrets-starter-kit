"""Verify an owner-transcribed age backup without copying or printing it."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile


def isolated_environment(directory: Path, key_file: Path | None = None) -> dict:
    # SOPS loads default age/SSH identities in addition to an explicit key file.
    environment = {name: value for name, value in os.environ.items()
                   if name.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC",
                                       "PATHEXT", "TEMP", "TMP"}}
    for name in ("APPDATA", "LOCALAPPDATA", "USERPROFILE", "XDG_CONFIG_HOME"):
        environment[name] = str(directory.resolve())
    environment["SOPS_DECRYPTION_ORDER"] = "age"
    if key_file is not None:
        environment["SOPS_AGE_KEY_FILE"] = str(key_file.resolve())
    return environment


def attempt(ciphertext: Path, environment: dict, expected_digest: str, *, sops="sops") -> dict:
    try:
        process = subprocess.run(
            [sops, "decrypt", "--output-type", "json", str(ciphertext.resolve())],
            env=environment, capture_output=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"process_completed": False, "decrypted": False, "semantic_match": False}
    matched = False
    if process.returncode == 0:
        try:
            content = json.loads(process.stdout)
            canonical = json.dumps(content, sort_keys=True, ensure_ascii=False,
                                   separators=(",", ":")).encode()
            matched = hashlib.sha256(canonical).hexdigest() == expected_digest
        except (ValueError, UnicodeError):
            pass
    return {"process_completed": True, "decrypted": process.returncode == 0,
            "semantic_match": matched}


def verify_fixture(ciphertext: Path, key_file: Path, digest: str, directory: Path) -> dict:
    document = json.loads(ciphertext.read_bytes())
    metadata = document.get("sops", {})
    recipients = metadata.get("age", [])
    if (not recipients or any(not item.get("recipient", "").startswith("age1")
                              for item in recipients)
            or any(metadata.get(name) for name in ("kms", "gcp_kms", "azure_kv",
                                                   "hc_vault", "hckms", "pgp"))):
        raise ValueError("age_only_fixture_required")
    before = attempt(ciphertext, isolated_environment(directory), digest)
    restored = attempt(ciphertext, isolated_environment(directory, key_file), digest)
    after = attempt(ciphertext, isolated_environment(directory), digest)
    return {"ciphertext_sha256": hashlib.sha256(ciphertext.read_bytes()).hexdigest(),
            "expected_semantic_sha256": digest, "age_recipient_count": len(recipients),
            "negative_before": before, "restored_copy": restored, "negative_after": after,
            "passed": (before["process_completed"] and not before["decrypted"]
                       and restored["process_completed"] and restored["semantic_match"]
                       and after["process_completed"] and not after["decrypted"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = {"schema_version": 1, "run_id": "SOPS-RESTORE-001",
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "context": {"platform": platform.system(), "python": platform.python_version(),
                          "owner_reported_physical_transcription": True,
                          "child_environment_allowlisted": True,
                          "plaintext_file_created": False, "private_key_copied": False,
                          "cloud_used": False, "ci_used": False,
                          "temporary_restored_copy_deleted": False},
              "fixtures": {}, "completed": False}
    if arguments.output.exists():
        print("Report already exists; no verification executed.")
        return 2
    try:
        if platform.system() != "Windows":
            raise ValueError("validated_isolation_requires_windows")
        if (arguments.key_file.is_symlink() or not arguments.key_file.is_file()
                or not 0 < arguments.key_file.stat().st_size <= 4096
                or arguments.key_file.resolve().is_relative_to(root)
                or arguments.key_file.resolve().is_relative_to(arguments.case_root.resolve())):
            raise ValueError("invalid_external_restore_file")
        for name, repository in (("framework", root), ("case", arguments.case_root)):
            status = subprocess.run(["git", "status", "--porcelain"], cwd=repository,
                                    capture_output=True, check=True)
            if status.stdout.strip():
                raise ValueError("source_not_clean")
            report[name + "_commit"] = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repository,
                capture_output=True, check=True, text=True).stdout.strip()
        with tempfile.TemporaryDirectory(prefix="sops-restore-isolation-") as directory:
            isolation = Path(directory)
            fixtures = {
                "framework_synthetic": (root / "examples/sops/secrets.enc.json",
                    (root / "examples/sops/expected-semantic-sha256.txt").read_text().strip()),
                "case_synthetic": (arguments.case_root / "examples/sops/secrets.enc.json",
                    "783f6c6935c089a67c4459464cfb1ed0a3742f7bf5ce2236ddcc0dad7c125311"),
            }
            for name, (ciphertext, digest) in fixtures.items():
                if not re.fullmatch("[0-9a-f]{64}", digest):
                    raise ValueError("invalid_semantic_digest")
                report["fixtures"][name] = verify_fixture(ciphertext, arguments.key_file,
                                                         digest, isolation)
        report["isolation_directory_removed"] = not Path(directory).exists()
        report["completed"] = (len(report["fixtures"]) == 2
                               and all(item["passed"] for item in report["fixtures"].values())
                               and report["isolation_directory_removed"])
    except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError):
        report["error_category"] = "restore_failed_sensitive_details_suppressed"
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with arguments.output.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"completed": report["completed"],
                      "fixture_results": {name: item["passed"]
                                          for name, item in report["fixtures"].items()},
                      "temporary_copy_deleted": False}))
    return 0 if report["completed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
