from __future__ import annotations

from .config import ProjectConfig


def application_files(config: ProjectConfig) -> dict[str, bytes]:
    """A small editable Python Functions example, separate from the kit runtime."""

    readme = f"""# {config.project_name}: comenzar a desarrollar

Este directorio es un ejemplo nuevo, no una copia de PyroPrev. El kit preparó
controles de credenciales, infraestructura y una Function HTTP mínima para el
perfil Python 3.12. No creó una base de datos ni publicó código en Azure.

## Qué editar y dónde

| Ruta | Acción del equipo |
|---|---|
| `app/` | Escribir aquí la lógica Python de la aplicación. `health.py` es solo un ejemplo. |
| `function_app.py` | Registrar las rutas HTTP de Azure Functions y llamar a `app/`. |
| `tests/` | Agregar pruebas del código propio. |
| `requirements.txt` | Declarar dependencias Python al incorporarlas; revisar compatibilidad con Python 3.12. |
| `feria-project.json` | Revisar el registro no secreto del perfil. Si cambia una decisión, modifica la entrada original y genera en otro directorio; no desincronices este JSON y `infra/bicep/main.bicepparam`. |
| `.env.example` | Documentar nombres de variables sin valores sensibles; los `.env` reales quedan fuera de Git. |
| `framework/`, `.feria/manifest.json` | Runtime y manifiesto del kit: no son el lugar para programar. |
| `infra/`, `.github/workflows/` | Revisar antes de cambiarlos; son controles e infraestructura, no código de negocio. |

La aplicación de ejemplo responde en `/api/health` cuando se ejecuta bajo el
host de Azure Functions. Puedes comprobar su lógica sin instalar dependencias:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Esa prueba no inicia el host ni comprueba Azure. Para ejecutar Functions
localmente se necesitan herramientas y dependencias adicionales, que el kit
no instala. No añadas claves reales a `local.settings.json`, `.env`, pruebas
o Git. `local.settings.json` está excluido y bloqueado por el control local.

## Primer repositorio y GitHub

1. Lee los archivos de esta tabla y confirma que el perfil fijo sirve para tu
   proyecto. Si ya existe una aplicación, conserva su estructura: no copies
   su código a `framework/` ni sobreescribas archivos con el generador.
2. Modifica `app/`, `function_app.py` y `tests/` para tu necesidad. Antes del
   primer commit, ejecuta las pruebas y revisa `git status` y `git diff`.
3. Antes del primer commit, instala `pre-commit` si falta, con una versión
   acordada por el equipo. Desde la raíz del proyecto ejecuta:

   ```powershell
   git init -b main
   git add .
   git diff --cached --name-only
   pre-commit install
   pre-commit run --all-files
   python -m unittest discover -s tests -p "test_*.py"
   git commit -m "Inicializar proyecto con controles DevSecOps"
   ```

   Si ya es un repositorio Git, omite `git init`. Revisa la lista staged:
   `local.settings.json`, `.env` y claves privadas nunca deben aparecer.
   No continúes si un control falla; investiga el hallazgo sin imprimirlo.
4. Crea en GitHub un repositorio **privado y vacío**. Copia su URL HTTPS,
   reemplaza el ejemplo siguiente y publica el commit revisado:

   ```powershell
   git remote add origin 'https://github.com/ORGANIZACION/REPO-PRIVADO.git'
   git push -u origin main
   ```

   El workflow activo `secret-scan.yml` escanea ese push y los pull requests.
   Verifica su resultado; si el plan del repositorio lo permite, exige ese
   check antes de integrar cambios. El repo privado no sustituye los controles.

Los dos workflows Azure se guardaron en `examples/azure-workflows/`, fuera de
`.github/workflows/`. **No están activos**. Contienen valores del ensayo
PyroPrev y requieren un diseño de identidad OIDC, permisos, parámetros y
revisión de costos específicos de cada equipo. No los copies ni ejecutes sin
adaptarlos. El kit tampoco trae un workflow que publique tu aplicación:
el plan Bicep describe recursos, pero subir código es una tarea separada.

## Alcance de esta versión

Se verificó generación, idempotencia y compilación local del perfil; el
ejemplo nuevo no ha completado un ciclo de publicación Cloud. El resultado
histórico de PyroPrev pertenece a otro repositorio y no demuestra que este
esqueleto funcione en Azure sin adaptación. SOPS se omite si no proporcionaste
destinatarios públicos `age`; no se comparte una clave privada entre alumnos.
"""

    files = {
        "README.md": readme,
        "app/__init__.py": '"""Application logic owned by the project team."""\n',
        "app/health.py": (
            '"""Small non-sensitive example; replace with your own application."""\n\n'
            "def health_payload() -> dict[str, str]:\n"
            '    return {"status": "ok"}\n'
        ),
        "function_app.py": (
            '"""HTTP entry point for the validated Python Functions profile."""\n\n'
            "import json\n\n"
            "import azure.functions as func\n\n"
            "from app.health import health_payload\n\n"
            "app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)\n\n\n"
            '@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)\n'
            "def health(request: func.HttpRequest) -> func.HttpResponse:\n"
            "    # Only a non-sensitive health response is public. Protect new routes.\n"
            "    return func.HttpResponse(\n"
            "        json.dumps(health_payload()),\n"
            '        mimetype="application/json",\n'
            "        status_code=200,\n"
            '        headers={"Cache-Control": "no-store"},\n'
            "    )\n"
        ),
        "host.json": '{"version": "2.0", "extensions": {"http": {"routePrefix": "api"}}}\n',
        "requirements.txt": "azure-functions==1.25.0\n",
        "tests/test_app.py": (
            "import unittest\n\n"
            "from app.health import health_payload\n\n\n"
            "class HealthTests(unittest.TestCase):\n"
            "    def test_health_response_has_no_sensitive_data(self):\n"
            '        self.assertEqual(health_payload(), {"status": "ok"})\n\n\n'
            'if __name__ == "__main__":\n'
            "    unittest.main()\n"
        ),
        "scripts/check_local_settings.py": (
            '"""Reject a force-added Azure Functions local settings file."""\n\n'
            "import sys\n"
            "from pathlib import Path\n\n\n"
            "def main(paths: list[str]) -> int:\n"
            '    blocked = [path for path in paths if Path(path).name.lower() == "local.settings.json"]\n'
            "    if blocked:\n"
            '        print("Refusing local.settings.json; keep local secrets outside Git.", file=sys.stderr)\n'
            "        return 1\n"
            "    return 0\n\n\n"
            'if __name__ == "__main__":\n'
            "    raise SystemExit(main(sys.argv[1:]))\n"
        ),
    }
    return {name: content.encode("utf-8") for name, content in files.items()}
