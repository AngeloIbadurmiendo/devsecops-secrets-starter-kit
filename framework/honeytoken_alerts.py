"""Opt-in local process notification; accepts only a fixed sanitized event."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys


def deliver_local_alert(output, event):
    payload = {"schema_version": 1, "phase": "alerted",
               "source_event_at_utc": event["at_utc"], "synthetic": True}
    try:
        result = subprocess.run(
            [sys.executable, "-m", "framework.honeytoken_alerts", "--output", str(output)],
            cwd=Path(__file__).resolve().parents[1], input=json.dumps(payload),
            capture_output=True, text=True, timeout=3)
        return result.returncode == 0 and json.loads(result.stdout) == {"saved": True}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return False


def receive_local_alert(output, payload):
    required = {"schema_version", "phase", "source_event_at_utc", "synthetic"}
    if (not isinstance(payload, dict) or set(payload) != required
            or type(payload["schema_version"]) is not int or payload["schema_version"] != 1
            or payload["phase"] != "alerted" or payload["synthetic"] is not True
            or not isinstance(payload["source_event_at_utc"], str)
            or len(payload["source_event_at_utc"]) > 40):
        raise ValueError("invalid sanitized event")
    timestamp = datetime.fromisoformat(payload["source_event_at_utc"])
    if timestamp.utcoffset() != timezone.utc.utcoffset(timestamp):
        raise ValueError("UTC event required")
    receipt = {"schema_version": 1, "event_type": "local_honeytoken_alert",
               "source_event_at_utc": payload["source_event_at_utc"],
               "received_at_utc": datetime.now(timezone.utc).isoformat(),
               "synthetic": True, "value_retained": False,
               "requires_operator_review": True}
    # Never overwrite an earlier alert; no implicit directory creation.
    with Path(output).open("x", encoding="utf-8", newline="\n") as target:
        json.dump(receipt, target, indent=2)
        target.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(2049)
        if len(raw) > 2048:
            raise ValueError("event too large")
        receive_local_alert(args.output, json.loads(raw.decode("utf-8")))
    except (OSError, ValueError, TypeError, OverflowError):
        print('{"saved": false}')
        return 1
    print('{"saved": true}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
