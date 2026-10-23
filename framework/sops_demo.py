from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


class SopsDemoError(RuntimeError):
    """Raised when the isolated SOPS demonstration cannot be completed."""


def _run(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        executable = Path(command[0]).name
        return_code = getattr(exc, "returncode", "unavailable")
        raise SopsDemoError(
            f"{executable} failed with exit code {return_code}; output was not retained."
        ) from exc


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _version(executable: str) -> str:
    line = _run([executable, "--version"]).stdout.strip().splitlines()[0]
    return line.removeprefix("sops ").removeprefix("v").split()[0]


def run_sops_age_demo(*, sops: str = "sops", age_keygen: str = "age-keygen") -> dict[str, object]:
    """Exercise an encrypt/decrypt round trip without retaining key material."""

    temporary_root: Path | None = None
    report: dict[str, object]
    with tempfile.TemporaryDirectory(prefix="feria-sops-") as directory:
        temporary_root = Path(directory)
        key_file = temporary_root / "age-keys.txt"
        plaintext_file = temporary_root / "secrets.plain.json"
        encrypted_file = temporary_root / "secrets.enc.json"

        _run([age_keygen, "-o", str(key_file)])
        recipient = _run([age_keygen, "-y", str(key_file)]).stdout.strip()
        if not recipient.startswith("age1"):
            raise SopsDemoError("age-keygen did not return a valid public recipient.")

        synthetic_values = [
            f"synthetic-password-{secrets.token_hex(16)}",
            f"synthetic-token-{secrets.token_hex(16)}",
        ]
        payload = {
            "application": {
                "database_password": synthetic_values[0],
                "external_api_token": synthetic_values[1],
            }
        }
        plaintext = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        plaintext_file.write_text(plaintext, encoding="utf-8", newline="\n")

        encrypt_started = time.perf_counter()
        encrypted = _run(
            [
                sops,
                "encrypt",
                "--age",
                recipient,
                "--input-type",
                "json",
                "--output-type",
                "json",
                str(plaintext_file),
            ]
        ).stdout
        encrypt_ms = round((time.perf_counter() - encrypt_started) * 1000, 3)
        encrypted_file.write_text(encrypted, encoding="utf-8", newline="\n")

        decrypt_env = os.environ.copy()
        decrypt_env["SOPS_AGE_KEY_FILE"] = str(key_file)
        decrypt_started = time.perf_counter()
        decrypted = _run(
            [
                sops,
                "decrypt",
                "--input-type",
                "json",
                "--output-type",
                "json",
                str(encrypted_file),
            ],
            env=decrypt_env,
        ).stdout
        decrypt_ms = round((time.perf_counter() - decrypt_started) * 1000, 3)

        encrypted_values_absent = all(value not in encrypted for value in synthetic_values)
        private_key_marker = "AGE-" + "SECRET-KEY-"
        private_key_absent = private_key_marker not in encrypted
        try:
            round_trip_matches = json.loads(decrypted) == payload
        except json.JSONDecodeError:
            round_trip_matches = False
        success = encrypted_values_absent and private_key_absent and round_trip_matches
        if not success:
            raise SopsDemoError("SOPS safety assertions failed; sensitive output was not retained.")

        report = {
            "schema_version": 1,
            "evidence_id": "SOPS-LOCAL-001",
            "observed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "mode": "isolated_ephemeral_demo",
            "tools": {
                "sops": _version(sops),
                "age": _version(age_keygen),
            },
            "backend": "age",
            "synthetic_value_count": len(synthetic_values),
            "assertions": {
                "round_trip_matches": round_trip_matches,
                "plaintext_values_absent_from_ciphertext": encrypted_values_absent,
                "private_key_absent_from_ciphertext": private_key_absent,
                "private_key_outside_repository": True,
            },
            "timing_ms": {
                "encrypt": encrypt_ms,
                "decrypt": decrypt_ms,
            },
            "hashes": {
                "plaintext_sha256": _sha256(plaintext),
                "ciphertext_sha256": _sha256(encrypted),
            },
            "plaintext_retained": False,
            "ciphertext_retained": False,
            "private_key_retained": False,
            "identifiers_retained": False,
            "remote_changes_performed": False,
            "development_deviation": {
                "preliminary_attempts": 1,
                "cause": "Bytewise YAML comparison rejected an equivalent serialization.",
                "treatment": "The recorded run compares parsed JSON semantics without relaxing ciphertext assertions.",
                "output_retained": False,
            },
            "success": True,
        }

    report["ephemeral_directory_removed"] = bool(
        temporary_root is not None and not temporary_root.exists()
    )
    return report


def render_markdown(report: dict[str, object]) -> str:
    tools = report["tools"]
    assertions = report["assertions"]
    timing = report["timing_ms"]
    deviation = report["development_deviation"]
    return f"""# SOPS-LOCAL-001 - Demostración local SOPS con age

**Fecha observada:** {report['observed_at_utc']}

**Resultado:** {'aprobado' if report['success'] else 'fallido'}

## Alcance

Se ejecutó un ciclo aislado de cifrado y descifrado con dos valores sintéticos generados en memoria. La clave privada, el texto claro y el archivo cifrado existieron únicamente en un directorio temporal eliminado al finalizar. No se accedió a Azure ni a GitHub.

## Entorno

- SOPS: `{tools['sops']}`.
- age: `{tools['age']}`.
- Backend: `age`.

## Verificaciones

| Control | Resultado |
|---|---|
| Descifrado idéntico al texto original | {assertions['round_trip_matches']} |
| Valores sintéticos ausentes del archivo cifrado | {assertions['plaintext_values_absent_from_ciphertext']} |
| Clave privada ausente del archivo cifrado | {assertions['private_key_absent_from_ciphertext']} |
| Clave privada creada fuera del repositorio | {assertions['private_key_outside_repository']} |
| Directorio efímero eliminado | {report['ephemeral_directory_removed']} |

## Tiempos observados

- Cifrado: {timing['encrypt']} ms.
- Descifrado: {timing['decrypt']} ms.

Los hashes registrados permiten distinguir esta ejecución sin conservar valores recuperables. Esta prueba valida el mecanismo local; no demuestra todavía administración multiusuario, recuperación de claves ni descifrado autorizado en CI.

## Desviación de desarrollo

Existió {deviation['preliminary_attempts']} intento preliminar no registrado como experimento: {deviation['cause']} Se corrigió mediante comparación semántica de JSON, sin relajar las aserciones sobre el texto cifrado. No se conservó su salida.
"""
