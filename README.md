# Kit DevSecOps para proyectos académicos

[![Secret scanning](../../actions/workflows/secret-scan.yml/badge.svg)](../../actions/workflows/secret-scan.yml)
[![Tests](../../actions/workflows/tests.yml/badge.svg)](../../actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Kit para que un equipo parta un proyecto de Python con Azure Functions sin
credenciales en Git. Genera un proyecto con escaneo de secretos local
(pre-commit y Gitleaks) y en GitHub Actions, un perfil Bicep para Azure Functions
Flex Consumption, configuración cifrada opcional con SOPS y age, y un ejemplo
HTTP `/api/health` con pruebas. La versión actual es la 0.7.4.

Nació de mi Trabajo de Título sobre prevención de fugas de credenciales en
proyectos académicos con GitHub y Azure. El caso de estudio fue PyroPrev, un
proyecto de otro equipo; el kit genera un esqueleto nuevo y **no incluye su
código ni es una aplicación ya publicada en Azure**. Los nombres `feria-*` y
`.feria/` vienen del contexto original (la Feria de Software de la universidad)
y se mantienen por compatibilidad.

Así se ve la generación en local, sin Azure ni claves:

```text
$ python -m framework.starter_kit doctor --mode local
Mode: local
- python: ok (required)
- git: ok (required)
Ready

$ python -m framework.starter_kit generate --config project.json --output proyecto
Generated 32 files in proyecto
SOPS configuration omitted because no public recipients were supplied.
No remote resources were changed.
```

Hay dos recorridos distintos:

1. **Prueba local:** comprobar que el kit genera archivos, compila el plan y
   ejecuta el ejemplo sin Azure. Sigue la sección siguiente.
2. **Proyecto de equipo:** revisar lo generado, sustituir el ejemplo por código
   propio, probarlo y recién entonces subir un repositorio privado. La sección
   «Del ejemplo a un repositorio de equipo» explica qué se edita.

## Alcance del perfil

El único perfil validado usa Azure Functions Flex Consumption en `brazilsouth`,
Python 3.12 y base de datos `none`. El kit **no** permite elegir cualquier
servicio, base de datos o región. Entrega controles de credenciales, un runtime
del generador dentro del proyecto, un ejemplo HTTP `/api/health` y pruebas
básicas. SOPS solo se configura si proporcionas destinatarios públicos `age`;
sin ellos se omite `.sops.yaml`.

El workflow de escaneo sí se activa al subirlo a GitHub. Los workflows OIDC y
de ciclo Azure son ejemplos **inactivos** en `examples/azure-workflows/`; contienen
valores del ensayo y requieren adaptación antes de copiarlos a
`.github/workflows/`. El kit no publica código de aplicación en Azure.

## Requisitos de la prueba local

En Windows, abre PowerShell en la **raíz de este repositorio**. Necesitas
Python 3.11 o posterior y Git. Para llegar hasta `plan`, necesitas Azure CLI
con Bicep disponible localmente: este paso solo compila infraestructura.
`pre-commit` se necesita al instalar el hook en un repositorio Git.

`doctor --mode local` comprueba Python y Git, pero **no** Azure CLI, Bicep o
`pre-commit`. No instales ni actualices nada por esta prueba sin decidirlo
antes.

## Prueba segura en cinco pasos

Copia el siguiente bloque en PowerShell desde la raíz del clon. Crea una carpeta
temporal nueva en cada ejecución. No necesita claves, no publica un repositorio
y no crea recursos Cloud.

```powershell
$demoRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('feria-kit-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
$expiryDate = (Get-Date).AddDays(30).ToString('yyyy-MM-dd')
$inputConfig = Join-Path $demoRoot 'entrada/feria-project.json'
$projectDir = Join-Path $demoRoot 'proyecto'

python -m framework.starter_kit doctor --mode local
python -m framework.starter_kit init --name feria-ejemplo --expires-on $expiryDate --non-interactive --output $inputConfig
python -m framework.starter_kit generate --config $inputConfig --output $projectDir
python -m framework.starter_kit plan --config (Join-Path $projectDir 'feria-project.json') --output (Join-Path $projectDir '.feria/plan.json')
```

`doctor` comprueba lo básico; `init` guarda decisiones no secretas; `generate`
crea el proyecto; `plan` compila Bicep **localmente**, sin `--what-if` ni acceso
a Azure Resource Manager. Después, en la **misma sesión**, entra al proyecto:

```powershell
Set-Location $projectDir
Test-Path .\.feria\plan.json
python -m unittest discover -s tests -p "test_*.py"
Get-Content .\README.md
```

`Test-Path` debe mostrar `True`. Si abriste otra terminal y `$projectDir` ya no
existe, entra manualmente en la carpeta `proyecto` generada y ejecuta solo los
tres comandos relativos de las últimas líneas. Allí hay un `README.md` propio
que explica qué editar. En esta prueba no debería existir `.sops.yaml`.

No edites la carpeta temporal para concluir la prueba. Si deseas repetir
`generate`, hazlo antes de tocar archivos; el manifiesto debe permanecer igual.
Una vez que el equipo modifica un archivo generado, el kit rechaza la
sobrescritura para proteger su trabajo. Genera otra propuesta en otra carpeta
y revisa diferencias en lugar de borrar cambios.

## Del ejemplo a un repositorio de equipo

La guía detallada está en el `README.md` **del proyecto generado**. Esta tabla
resume las responsabilidades:

| Ruta | Acción del equipo |
|---|---|
| `app/` | Desarrollar la lógica Python propia. `health.py` es un ejemplo reemplazable. |
| `function_app.py` | Registrar rutas HTTP para Azure Functions y conectar `app/`. |
| `tests/` | Probar el comportamiento de la aplicación del equipo. |
| `requirements.txt` | Añadir dependencias revisando compatibilidad con Python 3.12. |
| `feria-project.json` | Revisar nombre, ambiente y vencimiento; para cambiarlos, ajustar la entrada y generar en otra carpeta. No desincronizar este JSON de Bicep. |
| `.env.example` | Documentar nombres de variables sin valores sensibles. |
| `framework/`, `.feria/` | Runtime y manifiesto del kit; no programar aquí. |
| `infra/`, `.github/workflows/` | Infraestructura y controles; revisar antes de modificarlos. |
| `examples/azure-workflows/` | Demos inactivas; no copiar sin configuración OIDC, revisión de permisos y costos. |

Para un **proyecto nuevo de Python Functions**, el equipo puede convertir la
carpeta generada en su repositorio privado después de adaptar el ejemplo. El
README generado contiene la secuencia exacta para preparar Git, instalar el
hook, revisar los archivos staged, crear un repositorio privado vacío y hacer
el primer push. Al subirlo, hay que comprobar que el escaneo CI se ejecuta y,
si los permisos del repositorio lo permiten, exigirlo antes del merge. La
carpeta temporal de esta demostración no debe subirse sin esa revisión.

Para una **aplicación existente o un stack distinto**, genera primero en una
carpeta separada. Integra solo los controles compatibles sobre una rama de
trabajo; no copies el código a `framework/` ni reemplaces la estructura de la
aplicación. El generador detecta colisiones de contenido, pero no puede decidir
la arquitectura de cualquier equipo. PyroPrev requirió una adaptación
controlada, no un solo comando.

Subir el repositorio y comenzar a programar **no equivale a desplegar**.
El plan Bicep describe recursos, pero todavía falta integrar y probar la
publicación del código. Para esa etapa consulta [OIDC](docs/OIDC.md) y el
[ciclo Azure](docs/AZURE_LIFECYCLE.md), verifica tu propia suscripción,
permisos y cuotas, y revisa `what-if` antes de solicitar `apply`. **No
ejecutes `apply` o `destroy` por haber completado la prueba local.**

SOPS es opcional cuando no necesitas versionar configuración sensible. La
[guía SOPS](docs/SOPS.md) explica destinatarios públicos, respaldo y
recuperación. Nunca coloques una clave privada, token real o `.env` histórico
en el kit o en Git. `local.settings.json` queda excluido y bloqueado por el
control local. La [guía de escaneo](docs/CI_SECRET_SCANNING.md) explica el gate.

Si `doctor` dice «Ready» pero `plan` falla, comprueba `az bicep version`:
`doctor --mode local` no exige Azure CLI/Bicep. Si `init` indica fecha pendiente,
usa un `expires_on` futuro. Si otro archivo ya existe y difiere, el generador
se detiene sin sobrescribirlo.

## Decisiones técnicas

El perfil de Azure es deliberadamente pequeño: Functions Flex Consumption con
Python 3.12, 512 MB, una instancia máxima y sin instancias siempre activas, para
que quepa en créditos estudiantiles, sin depender de Pay-As-You-Go, y se pueda
crear y destruir de forma reproducible. Dejé la base de datos fuera
(`database_profile=none`) porque la consulta de SKUs de MySQL falló en tres
regiones y no aportaba a lo que había que demostrar, que eran los controles de
credenciales; el trade-off es que el ejemplo no cubre una aplicación con
persistencia.

La autenticación entre GitHub y Azure usa OIDC, sin un secreto permanente en el
repositorio, y los workflows que tocan Azure son demos de ejecución manual,
inactivas hasta que el equipo las adapta. Para la configuración sensible elegí
SOPS con destinatarios `age` individuales: es gratuito y portable, pero deja la
custodia de las claves en cada persona, así que la clave de CI tiene alcance
propio y los respaldos se documentan en la [guía SOPS](docs/SOPS.md).

En CI, las acciones y los binarios descargados van fijados por commit y SHA-256
(ver [modelo de amenazas](docs/THREAT_MODEL.md)), y el generador se niega a
sobrescribir archivos que el equipo ya modificó. Cada decisión con su contexto y
su criterio de reversión está en [`docs/adr/`](docs/adr).

## Investigación y evidencia

Este kit surge de un Trabajo de Título sobre prevención de fugas de credenciales
en proyectos académicos con GitHub y Azure. La evidencia experimental completa
no se incluye aquí; las decisiones técnicas están en [`docs/adr/`](docs/adr). La generación automatizada, la prueba
manual del autor y este ejemplo no prueban por sí solos facilidad de adopción
para todos los equipos ni funcionamiento Cloud del nuevo esqueleto. Consulta
[SECURITY.md](SECURITY.md) antes de usarlo.
