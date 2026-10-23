#!/usr/bin/env python3
"""Generate a deterministic corpus containing only synthetic, invalid credentials."""

from __future__ import annotations

import argparse
import hashlib
import json
import string
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SEED = "pyroprev-thesis-corpus-v1"
ALPHANUM = string.ascii_letters + string.digits
UPPER_DIGITS = string.ascii_uppercase + string.digits
URL_SAFE = string.ascii_letters + string.digits + "_-"


@dataclass(frozen=True)
class CorpusCase:
    case_id: str
    classification: str
    filename: str
    format_name: str
    content: str


def deterministic_fragment(seed: str, label: str, length: int, alphabet: str = ALPHANUM) -> str:
    """Map SHA-256 bytes to a stable alphabet without relying on random state."""
    if length < 1:
        raise ValueError("length must be positive")
    if not alphabet:
        raise ValueError("alphabet cannot be empty")
    output: list[str] = []
    counter = 0
    while len(output) < length:
        block = hashlib.sha256(f"{seed}|{label}|{counter}".encode("utf-8")).digest()
        output.extend(alphabet[value % len(alphabet)] for value in block)
        counter += 1
    return "".join(output[:length])


def build_cases(seed: str = DEFAULT_SEED) -> list[CorpusCase]:
    """Create representative positives and benign high-entropy controls."""
    positives = [
        CorpusCase(
            case_id="POS-GITHUB-001",
            classification="positive",
            filename="github_classic_pat.env",
            format_name="GitHub classic personal access token",
            content=f"GITHUB_TOKEN=ghp_{deterministic_fragment(seed, 'github-pat', 36)}\n",
        ),
        CorpusCase(
            case_id="POS-AWS-001",
            classification="positive",
            filename="aws_access_key.env",
            format_name="AWS access key identifier",
            content=f"AWS_ACCESS_KEY_ID=AKIA{deterministic_fragment(seed, 'aws-key-id', 16, UPPER_DIGITS)}\n",
        ),
        CorpusCase(
            case_id="POS-GCP-001",
            classification="positive",
            filename="google_api_key.env",
            format_name="Google API key",
            content=f"GOOGLE_API_KEY=AIzaSy{deterministic_fragment(seed, 'google-api-key', 33, URL_SAFE)}\n",
        ),
        CorpusCase(
            case_id="POS-STRIPE-001",
            classification="positive",
            filename="stripe_secret.env",
            format_name="Stripe live secret key",
            content=f"STRIPE_SECRET_KEY=sk_live_{deterministic_fragment(seed, 'stripe-secret', 24)}\n",
        ),
    ]
    benign = [
        CorpusCase(
            case_id="NEG-SHA256-001",
            classification="benign",
            filename="sha256.txt",
            format_name="SHA-256 build digest",
            content=f"BUILD_DIGEST={hashlib.sha256(f'{seed}|digest'.encode()).hexdigest()}\n",
        ),
        CorpusCase(
            case_id="NEG-UUID-001",
            classification="benign",
            filename="uuid.txt",
            format_name="UUID-like trace identifier",
            content="TRACE_ID=123e4567-e89b-12d3-a456-426614174000\n",
        ),
        CorpusCase(
            case_id="NEG-PUBLIC-001",
            classification="benign",
            filename="public_identifier.txt",
            format_name="Public opaque identifier",
            content=f"PUBLIC_IDENTIFIER={deterministic_fragment(seed, 'public-id', 48)}\n",
        ),
        CorpusCase(
            case_id="NEG-EXAMPLE-001",
            classification="benign",
            filename="documentation_value.txt",
            format_name="Explicit documentation placeholder",
            content="DOCUMENTATION_VALUE=replace-me-during-deployment\n",
        ),
    ]
    return positives + benign


def file_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def generate_corpus(output: Path, seed: str = DEFAULT_SEED) -> dict[str, object]:
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    cases = build_cases(seed)
    manifest_cases: list[dict[str, object]] = []
    for case in cases:
        destination = output / case.classification / case.filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(case.content, encoding="utf-8", newline="\n")
        manifest_cases.append(
            {
                "case_id": case.case_id,
                "classification": case.classification,
                "file": f"{case.classification}/{case.filename}",
                "format": case.format_name,
                "expected_detection": case.classification == "positive",
                "sha256": file_digest(case.content),
            }
        )

    manifest: dict[str, object] = {
        "schema_version": 1,
        "generator": "scripts/generate_corpus.py",
        "seed_sha256": hashlib.sha256(seed.encode("utf-8")).hexdigest(),
        "safety": "All credential-like values are deterministic, synthetic, locally generated and never issued by a provider.",
        "cases": manifest_cases,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    manifest = generate_corpus(args.output, args.seed)
    positive = sum(case["classification"] == "positive" for case in manifest["cases"])
    benign = sum(case["classification"] == "benign" for case in manifest["cases"])
    print(f"Generated {positive} positive and {benign} benign synthetic cases in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

