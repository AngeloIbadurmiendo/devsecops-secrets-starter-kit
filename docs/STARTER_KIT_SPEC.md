# Especificación del kit de inicio seguro para la Feria

## Propósito

El kit traduce los controles del framework a una experiencia reproducible de adopción para equipos de proyectos académicos. Es un entregable técnico derivado de un trabajo de investigación, no una nueva pregunta de investigación ni un configurador universal de Azure.

Su aporte se evaluará por la facilidad con que un equipo puede instalar una línea base segura, inspeccionar el cambio propuesto y obtener un entorno académico eliminable. PyroPrev será el caso principal usado para diseñar y verificar el perfil inicial.

**Actualización de incorporación (20 de septiembre de 2026):** el autoensayo
manual del autor con la guía anterior alcanzó generación y plan local, pero
calificó su claridad con 3/5 sin ayuda y 4/5 con asistencia. La versión 0.7.4
incluye un README dentro del proyecto, lógica de ejemplo en `app/`, entrada
`function_app.py`, pruebas locales y demos Azure inactivas bajo `examples/`.
Esta ampliación facilita empezar a programar en el perfil Python, pero no
demuestra publicación Cloud del nuevo esqueleto ni adopción por otros equipos.
Los datos E5-LOCAL-001 permanecen asociados a la versión congelada anterior.

## Usuario y escenario

- Equipo académico de aproximadamente seis integrantes.
- Repositorio privado en GitHub y GitHub Actions.
- Cuentas institucionales con GitHub Student Developer Pack.
- Suscripción Azure for Students individual, sin tarjeta ni migración a pago por uso.
- Proyecto de duración acotada que prioriza costo controlado, seguridad básica y eliminación al finalizar.

El kit no compartirá cuentas, credenciales ni créditos entre integrantes. Cada despliegue pertenecerá a una identidad y suscripción claramente identificadas.

## Arquitectura propuesta

Azure CLI y Bicep son el motor del ciclo de vida. Una capa delgada en Python
realiza el diagnóstico previo, recoge decisiones acotadas, valida guardas y
genera configuración versionable. El wrapper no reimplementa autenticación ni
estado de Azure.

Flujo previsto:

```text
doctor -> init -> generate -> plan -> apply -> verify -> destroy
```

Al 13 de septiembre de 2026 están implementados `doctor`, `init`, `generate`,
`plan`, `apply`, `verify` y `destroy`. El modo local de `plan` compila Bicep y
`plan --what-if` consulta ARM dentro de un grupo preparado. OIDC fue demostrado
primero con `Reader` y luego con permisos mutantes temporales limitados al grupo.
`AZ-LIFECYCLE-001` registra el ciclo Cloud completo y residuo Azure cero.

| Comando | Responsabilidad | Cambia recursos remotos |
|---|---|---|
| `doctor` | Verificar herramientas, autenticación, oferta, cuotas y prerrequisitos | No |
| `init` | Crear el archivo declarativo del proyecto mediante preguntas acotadas | No |
| `generate` | Generar controles, workflows, Bicep y documentación | No |
| `plan` | Mostrar diferencias mediante validación y `what-if` | No |
| `apply` | Aprovisionar solo tras confirmación explícita | Sí |
| `verify` | Comprobar controles y salud mínima sin exponer secretos | Solo lectura |
| `destroy` | Eliminar el grupo de recursos tras confirmación explícita | Sí |

## Perfil MVP

El primer perfil verificable será deliberadamente estrecho. `AZ-PREFLIGHT-003` y `ADR-013` seleccionaron el siguiente candidato para implementación:

- API Python compatible con el caso PyroPrev;
- Azure Functions Flex Consumption en `brazilsouth`, Functions 4 y Python 3.12;
- 512 MB, una instancia máxima y cero instancias always-ready;
- cuenta Storage mínima `Standard_LRS` requerida por Functions;
- opción de base de datos `none` durante la primera validación;
- GitHub Actions con permisos mínimos y autenticación Azure mediante OIDC;
- detección local y remota de credenciales;
- configuración cifrada con SOPS;
- infraestructura Bicep etiquetada y eliminable;
- caducidad lógica, control manual de costo y guía de destrucción; el presupuesto
  nativo es opcional cuando la oferta estudiantil no expone esa funcionalidad.

Una opción MySQL solo se incorporará si aporta evidencia necesaria después del
perfil inicial. El despliegue FC1 demostró capacidad efectiva y destrucción
reproducible. `AZ-COST-001` observó USD 0 usados después del ciclo, pero el kit no
promete costo cero para otras cargas, ofertas o fechas.

## Archivo declarativo

Las elecciones quedarán en `feria-project.json`, un archivo revisable y sin valores secretos. Esquema inicial:

```json
{
  "schema_version": 1,
  "project_name": "ejemplo-feria",
  "environment": "dev",
  "azure_location": "brazilsouth",
  "compute_profile": "functions-flex-python",
  "database_profile": "none",
  "expires_on": "pending",
  "secret_scanning": true,
  "sops": true,
  "sops_age_recipients": [],
  "github_azure_oidc": true
}
```

La generación debe ser determinística e idempotente: ejecutar nuevamente el kit con las mismas entradas no debe producir diferencias inesperadas.

## Artefactos generados

- `.pre-commit-config.yaml` y `.gitleaks.toml`;
- workflow consumidor del escaneo reutilizable;
- workflow de despliegue mediante OIDC;
- `.sops.yaml` cuando existen destinatarios públicos válidos y guía de administración de claves;
- módulos Bicep y comandos de ciclo de vida;
- `.env.example`, `SECURITY.md` y runbook de operación;
- archivo de parámetros no secretos y comandos de verificación/destrucción.

Si el repositorio ya contiene `.gitignore`, el kit conserva su contenido y añade
únicamente los patrones de seguridad ausentes. Los demás archivos continúan bajo
una política de no sobrescritura cuando existe contenido ajeno.

El manifiesto `.feria/manifest.json` solo contiene metadatos y checksums SHA-256.
La configuración generada lo excluye mediante una regla de sufijo de ruta exacto para evitar
que los nombres de workflows con la palabra `secret` conviertan esos hashes en
falsos positivos; la exclusión no alcanza ningún otro archivo.

## Guardas para cuentas estudiantiles

- Fallar de forma segura si no se puede identificar la suscripción, oferta o región.
- No solicitar tarjetas, migración a Pay-As-You-Go ni transferencia de beneficios.
- No almacenar secretos de cliente de Azure; usar OIDC para CI/CD.
- Ejecutar validación y `what-if` antes del aprovisionamiento.
- Mostrar recursos y estimación/limitación disponible antes de confirmar.
- Etiquetar propietario, propósito, entorno y fecha prevista de eliminación.
- Mantener un único entorno mínimo por defecto.
- Proporcionar destrucción verificable y registrar recursos residuales.

Los beneficios gratuitos, SKU y cuotas cambian con el tiempo. Sus valores estarán versionados como supuestos verificables, no incrustados como garantías permanentes.

## Criterios de aceptación

1. En una instalación limpia, `doctor` identifica correctamente prerrequisitos y bloqueos.
2. El perfil genera todos los controles anunciados sin incorporar valores secretos.
3. La segunda generación con las mismas entradas no altera archivos.
4. Un commit limpio pasa los controles y una credencial sintética es bloqueada.
5. GitHub Actions se autentica en Azure sin secretos Cloud permanentes.
6. `plan` no crea recursos y permite revisar el alcance antes de aplicar.
7. El perfil anunciado se despliega, verifica y destruye con evidencia reproducible.
8. No quedan recursos residuales conocidos después de la destrucción.
9. La documentación permite repetir el proceso sin asistencia del autor o registra exactamente la ayuda requerida.

## Evaluación de adopción

La evaluación reutilizará el experimento E5 del protocolo de investigación. Las métricas mínimas serán:

- tiempo total de instalación y configuración;
- cantidad de pasos y decisiones manuales;
- errores recuperables y bloqueantes;
- solicitudes de ayuda;
- controles instalados correctamente;
- latencia adicional de CI;
- recursos creados, consumo observado y resultado de la destrucción.

La prueba principal puede ser una ejecución instrumentada por el autor en un entorno limpio. Una repetición por terceros será evidencia complementaria, no una dependencia para terminar la tesis.

## Límites explícitos

- No habrá interfaz gráfica en el MVP.
- No habrá soporte multi-cloud ni alta disponibilidad productiva.
- No se intentará cubrir todas las combinaciones de servicios Azure.
- No se agruparán ni rotarán créditos entre cuentas estudiantiles.
- No se reconstruirá PyroPrev completo.
- No se declarará una configuración como gratuita sin observación o fuente vigente.

## Secuencia de entrega

1. **G1:** detección local/CI y evidencia de bloqueo.
2. **G2a:** esqueleto `doctor/init/generate` y configuración declarativa.
3. **G2b:** SOPS, OIDC, Bicep, `plan/apply/verify/destroy` para un perfil.
4. **G3:** honeytoken controlado, alerta y respuesta.
5. **G4:** experimentos, evaluación de adopción y documentación final.

El wrapper se construirá junto con G2, reemplazando trabajo manual de integración. No agrega una fase independiente al cronograma.
