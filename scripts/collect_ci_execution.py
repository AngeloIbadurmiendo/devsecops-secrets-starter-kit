"""Collect allowlisted GitHub run/step metadata, not logs or billing estimates."""

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def github_json(arguments):
    result = subprocess.run(["gh", *arguments], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError("GitHub metadata query failed; raw output suppressed.")
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo) or not args.run.isdigit():
        raise ValueError("Invalid repository or run identity.")
    raw = github_json(["api", f"repos/{args.repo}/actions/runs/{args.run}"])
    jobs = github_json(["run", "view", args.run, "--repo", args.repo, "--json", "jobs"])["jobs"]
    data = {key: raw[key] for key in ("id", "run_attempt", "head_sha", "event", "status",
                                    "conclusion", "created_at", "run_started_at", "updated_at")}
    if data["status"] != "completed":
        raise ValueError("Collect only completed executions.")
    data["jobs"] = [{key: job[key] for key in ("name", "status", "conclusion", "startedAt", "completedAt")}
                    | {"steps": [{key: step[key] for key in ("name", "number", "status", "conclusion",
                                                           "startedAt", "completedAt")}
                                 for step in job["steps"]]} for job in jobs]
    data["collected_at_utc"] = datetime.now(timezone.utc).isoformat()
    data["billing_or_minutes_balance_queried"] = False
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print("Sanitized completed-run metadata collected; no logs or billing claims.")


if __name__ == "__main__":
    main()
