from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PRIVATE_KEY_MARKER = "AGE-" + "SECRET-KEY-"


class VerificationError(RuntimeError):
    """Raised when the SOPS CI demonstration violates an invariant."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _string_values(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for item in value.values():
            yield from _string_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _string_values(item)
    elif isinstance(value, str):
        yield value


def verify_demo(
    *,
    encrypted_path: Path,
    decrypted_path: Path,
    expected_digest_path: Path,
    metrics_path: Path,
    minimum_recipients: int = 2,
) -> dict[str, Any]:
    try:
        encrypted_text = encrypted_path.read_text(encoding="utf-8")
        encrypted = json.loads(encrypted_text)
        decrypted = json.loads(decrypted_path.read_text(encoding="utf-8"))
        expected_digest = expected_digest_path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError("The SOPS demonstration inputs are unreadable.") from exc

    if not SHA256_PATTERN.fullmatch(expected_digest):
        raise VerificationError("The expected semantic digest is invalid.")
    if not isinstance(decrypted, dict) or not decrypted:
        raise VerificationError("The decrypted document must be a non-empty object.")
    if not isinstance(encrypted, dict) or not isinstance(encrypted.get("sops"), dict):
        raise VerificationError("The encrypted document has no SOPS metadata.")

    age_entries = encrypted["sops"].get("age")
    if not isinstance(age_entries, list) or len(age_entries) < minimum_recipients:
        raise VerificationError("The encrypted document lacks recovery recipients.")
    recipients = [entry.get("recipient") for entry in age_entries if isinstance(entry, dict)]
    if len(recipients) != len(age_entries) or any(
        not isinstance(recipient, str) or not recipient.startswith("age1")
        for recipient in recipients
    ):
        raise VerificationError("The SOPS age recipient metadata is invalid.")
    if len(set(recipients)) != len(recipients):
        raise VerificationError("The SOPS age recipients must be distinct.")
    if PRIVATE_KEY_MARKER in encrypted_text:
        raise VerificationError("Private age key material appeared in the ciphertext.")

    actual_digest = hashlib.sha256(_canonical_json(decrypted)).hexdigest()
    if actual_digest != expected_digest:
        raise VerificationError("The decrypted semantic digest does not match.")
    if any(value and value in encrypted_text for value in _string_values(decrypted)):
        raise VerificationError("A plaintext value appeared in the ciphertext.")

    report = {
        "schema_version": 1,
        "status": "passed",
        "age_recipient_count": len(recipients),
        "ciphertext_sha256": hashlib.sha256(
            encrypted_text.encode("utf-8")
        ).hexdigest(),
        "plaintext_semantic_sha256": actual_digest,
        "assertions": {
            "semantic_digest_matches": True,
            "plaintext_values_absent_from_ciphertext": True,
            "private_key_absent_from_ciphertext": True,
            "distinct_recovery_paths_present": True,
        },
        "sensitive_values_recorded": False,
    }
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify a SOPS CI round trip without printing decrypted values."
    )
    parser.add_argument("--encrypted", type=Path, required=True)
    parser.add_argument("--decrypted", type=Path, required=True)
    parser.add_argument("--expected-digest-file", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = verify_demo(
            encrypted_path=args.encrypted,
            decrypted_path=args.decrypted,
            expected_digest_path=args.expected_digest_file,
            metrics_path=args.metrics,
        )
    except VerificationError as exc:
        print(f"SOPS CI demonstration failed: {exc}")
        return 1
    print(
        "SOPS CI demonstration passed with "
        f"{report['age_recipient_count']} independent recipients."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
