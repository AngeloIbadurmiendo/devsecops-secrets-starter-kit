"""One bounded local HTTP activation; save only a new, sanitized report."""

import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from framework.honeytoken import run_pilot
from framework.honeytoken_alerts import deliver_local_alert


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--alert-output", type=Path,
                        help="Opt-in sanitized receipt written by a separate local process")
    args = parser.parse_args()
    if args.alert_output:
        args.alert_output = args.alert_output.resolve()
        if args.alert_output.exists() or not args.alert_output.parent.is_dir():
            parser.error("alert output must be new with an existing parent directory")
    # Reserve output before any socket is opened; no overwrites or implicit mkdir.
    with args.output.open("x", encoding="utf-8") as output:
        root = Path(__file__).resolve().parents[1]
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                                capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                               capture_output=True, text=True, check=True).stdout.strip()
        try:
            sink = (lambda event: deliver_local_alert(args.alert_output, event)) if args.alert_output else None
            report = run_pilot(alert_sink=sink)
        except (OSError, RuntimeError):
            report = {"schema_version": 1, "evidence_id": "HONEY-LOCAL-001",
                      "passed": False, "error_category": "local_transport_or_cleanup_error",
                      "synthetic_value_retained": False, "identifiers_retained": False}
            if args.alert_output:
                report["evidence_id"] = "HONEY-IPC-001"
        report["framework_commit"] = commit
        report["worktree_dirty_at_execution"] = bool(dirty)
        report["python_version"] = platform.python_version()
        report["platform"] = platform.system()
        json.dump(report, output, indent=2)
        output.write("\n")
    print("Local canary pilot passed" if report["passed"] else "Local pilot failed; sanitized report saved")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
