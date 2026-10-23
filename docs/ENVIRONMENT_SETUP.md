# Entorno de desarrollo y verificación

Este procedimiento deja listo el entorno local y verifica el kit sin crear recursos Cloud. Instalar software cambia la máquina: hazlo de forma deliberada, no como parte automática de la verificación. Nunca copies tokens personales a archivos o comandos; usa el gestor de credenciales de Git y `gh auth login`.

## 1. Herramientas

| Herramienta | Necesaria para | Versión verificada (sep-2026) | Regla |
|---|---|---:|---|
| Python | kit, scripts y pruebas | 3.13.7 | Usar Python 3.11 o posterior |
| Git | el repositorio | 2.51.0 | Mantener credenciales fuera del remoto |
| `pre-commit` | control local | 4.6.0 | Instalar desde `requirements-dev.txt` |
| GitHub CLI (`gh`) | PR y Actions | 2.78.0 | Autenticar de forma interactiva |
| Azure CLI (`az`) | preflight y RBAC | 2.83.0 | Confirmar siempre la suscripción seleccionada |
| Azure Developer CLI (`azd`) | herramienta histórica del entorno, no usada por el kit actual | 1.33.0 | No requerida para `plan/apply` del kit |
| Bicep CLI | validación e infraestructura como código | 0.46.1 | Instalada mediante Azure CLI |
| SOPS | configuración cifrada versionable | 3.13.3 | No almacenar claves privadas en Git |
| age | backend inicial de claves SOPS | 1.3.1 | Cada usuario conserva su clave fuera del checkout |
| `actionlint` | validación adicional de workflows | 1.7.12 | Recomendado; CI y pruebas no dependen de una ruta local fija |

Estas versiones describen el entorno probado, no obligan a usar versiones futuras sin validación. Fuentes de instalación oficiales:

- [Python](https://www.python.org/downloads/)
- [Git](https://git-scm.com/downloads)
- [GitHub CLI](https://cli.github.com/)
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)
- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- [Bicep CLI](https://learn.microsoft.com/azure/azure-resource-manager/bicep/install)
- [SOPS](https://github.com/getsops/sops)
- [age](https://github.com/FiloSottile/age)
- [pre-commit](https://pre-commit.com/#install)
- [actionlint](https://github.com/rhysd/actionlint/releases/tag/v1.7.12)

En Windows, `azd` no es requisito del kit actual. Si se necesitan SOPS o age,
existen los paquetes `SecretsOPerationS.SOPS` y `FiloSottile.age` de winget;
Bicep puede gestionarse mediante Azure CLI. Instalar software cambia la
máquina y debe hacerse como una tarea autorizada, no como parte automática
de esta verificación.

## 2. Entorno Python reproducible

Desde la raíz del repositorio:

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

En Linux o macOS, activar el entorno equivalente:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

El código y las pruebas actuales usan la biblioteca estándar de Python. `requirements-dev.txt` fija la herramienta necesaria para ejecutar el hook local.

## 3. Verificación local

```powershell
git status --short --branch
python -m unittest discover -s tests -p "test_*.py" -v
pre-commit validate-config
pre-commit run --all-files
python -m framework.starter_kit doctor --mode local --json
```

Si `actionlint` está disponible en `PATH`:

```powershell
actionlint
```

`doctor --mode local` no valida Azure CLI, Bicep o `pre-commit`; revisar esos
requisitos por separado antes de usar `plan` o instalar el hook.

## 4. Smoke test del kit

Usar un directorio temporal nuevo; no apuntar a un proyecto real:

```powershell
$handoffOutput = Join-Path ([System.IO.Path]::GetTempPath()) 'kit-starter-smoke'
python -m framework.starter_kit init `
  --name proyecto-demo `
  --non-interactive `
  --output (Join-Path $handoffOutput 'project.json')
python -m framework.starter_kit generate `
  --config (Join-Path $handoffOutput 'project.json') `
  --output (Join-Path $handoffOutput 'generated')
```

El kit genera 23 archivos sin destinatarios SOPS (omite `.sops.yaml` y declara que
no realizó cambios remotos) y 24 con al menos un destinatario público válido.
El manifiesto es un archivo adicional. Repetir `generate` debe conservar el mismo
manifiesto.

## 5. Antes de usar Azure

Autenticarse no autoriza crear recursos. `az deployment ... create`, asignaciones RBAC y cambios OIDC solo se ejecutan tras una decisión explícita. Antes de cualquier operación, confirma la suscripción seleccionada:

```powershell
az account show --query "{name:name,state:state,isDefault:isDefault}" --output table
```

No conserves IDs de suscripción o tenant, correos ni tokens en la evidencia que generes.
