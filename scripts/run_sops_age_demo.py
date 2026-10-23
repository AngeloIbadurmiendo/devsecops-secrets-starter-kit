from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from framework.sops_demo import SopsDemoError, render_markdown, run_sops_age_demo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an isolated SOPS+age round trip and retain only sanitized evidence."
    )
    parser.add_argument("--sops", default="sops")
    parser.add_argument("--age-keygen", default="age-keygen")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("evidence/sops/SOPS-LOCAL-001.json"),
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("evidence/sops/SOPS-LOCAL-001.md"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_sops_age_demo(sops=args.sops, age_keygen=args.age_keygen)
    except SopsDemoError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    args.output_md.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    print(f"Sanitized evidence written to {args.output_json} and {args.output_md}")
    print("No key material, plaintext, ciphertext, or remote resources were retained.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
