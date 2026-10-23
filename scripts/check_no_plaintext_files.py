from __future__ import annotations

import sys
from pathlib import Path


PRIVATE_KEY_MARKER = b"AGE-" + b"SECRET-KEY-"


def forbidden_reason(path: Path) -> str | None:
    normalized = path.as_posix().lower()
    name = path.name.lower()
    if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
        return "environment file"
    if name == "local.properties":
        return "local configuration"
    if name.startswith("secrets.plain."):
        return "plaintext secret filename"
    if ".decrypted." in name or ".sops-dec." in name:
        return "decrypted secret filename"
    if "/.sops-age-keys/" in f"/{normalized}":
        return "private-key directory"
    if path.is_file():
        try:
            overlap = b""
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    inspected = overlap + chunk
                    if PRIVATE_KEY_MARKER in inspected:
                        return "age private-key material"
                    overlap = inspected[-(len(PRIVATE_KEY_MARKER) - 1) :]
        except OSError:
            return "unreadable file"
    return None


def main(paths: list[str] | None = None) -> int:
    candidates = paths if paths is not None else sys.argv[1:]
    blocked = []
    for raw_path in candidates:
        path = Path(raw_path)
        reason = forbidden_reason(path)
        if reason:
            blocked.append((path.as_posix(), reason))
    if not blocked:
        return 0
    print("Refusing plaintext or private-key files:", file=sys.stderr)
    for path, reason in blocked:
        print(f"- {path}: {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
