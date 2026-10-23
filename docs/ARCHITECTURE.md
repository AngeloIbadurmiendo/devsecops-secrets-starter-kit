# Arquitectura del framework

## Objetivo

Prevenir que credenciales ingresen al repositorio, detectar exposiciones existentes o históricas y desplegar el caso académico sin una credencial Azure permanente. La arquitectura privilegia controles pequeños, versionables y ejecutables con herramientas gratuitas.

## Vista lógica

```text
Desarrollador
   |
   v
pre-commit + Gitleaks ------> rechazo local
   |
   v
GitHub privado
   |
   v
GitHub Actions + Gitleaks --> artefacto SARIF redactado / rechazo del PR
   |
   +---- OIDC temporal -----> Azure (alcance mínimo)
   |                              |
   |                              +--> recursos Bicep eliminables
   |                              +--> alerta de honeytoken
   v
SOPS + archivos cifrados

Kit de inicio: doctor -> init -> generate -> plan -> apply -> verify -> destroy
Evidencia: métricas sanitizadas + commits + protocolo experimental
```

## Componentes y responsabilidades

| Capa | Componentes | Responsabilidad |
|---|---|---|
| Prevención local | `pre-commit`, Gitleaks | Rechazar una credencial antes de crear el commit |
| Detección remota | GitHub Actions, Gitleaks | Escanear árbol e historial y bloquear integración |
| Configuración | SOPS + destinatarios `age` | Versionar configuración cifrada sin conservar texto claro ni claves privadas en Git |
| Identidad Cloud | GitHub OIDC, RBAC Azure | Obtener credenciales temporales limitadas al repo, referencia y alcance |
| Infraestructura | Bicep, `azd`, Functions Flex Consumption y Storage | Planificar, crear, verificar y eliminar el perfil `functions-flex-python` |
| Adopción | Kit Python | Validar prerrequisitos y generar el perfil probado de forma idempotente |
| Respuesta | Honeytoken y playbook | Alertar una activación controlada y guiar contención |
| Evidencia | JSON/Markdown sanitizado | Vincular resultados con commits, versiones y ejecuciones |

## Fronteras de confianza

1. **Estación del desarrollador / repositorio:** el hook local reduce errores, pero puede omitirse; CI es el segundo control independiente.
2. **Repositorio / runner GitHub:** el workflow usa código versionado, permisos mínimos, acciones fijadas y binarios verificados.
3. **GitHub / Azure:** OIDC reemplaza secretos estáticos; Azure debe validar issuer, subject y audience.
4. **Datos cifrados / material descifrado:** SOPS permite versionar cifrado, pero el texto claro solo puede existir temporalmente en procesos autorizados.
5. **Entorno experimental / sistemas externos:** honeytokens y pruebas permanecen aislados y sin privilegios útiles.
6. **Ejecución / evidencia:** antes de persistir logs o reportes se eliminan valores y rutas innecesarias.

## Propiedades de seguridad esperadas

- defensa en profundidad entre control local y CI;
- fallo cerrado ante hallazgos o configuración inválida;
- ausencia de secretos Cloud permanentes en GitHub;
- mínimo privilegio e identidad trazable;
- evidencia redactada y con retención acotada;
- infraestructura revisable antes de crearla y eliminable al finalizar;
- generación determinística para distinguir cambios intencionales.

## Estado por gate

| Gate | Capacidad | Estado |
|---|---|---|
| G1 | Prevención local y detección CI | Validada con camino limpio y PR sintético rechazado |
| G2 | SOPS, OIDC, Bicep y kit | SOPS local/CI, OIDC, ciclo Cloud y salud Flask mínima observada; portabilidad del lifecycle del caso pendiente; no API histórica completa ni estabilidad |
| G3 | Honeytoken y respuesta | Integración opt-in Flask mínima y E4-LOCAL-001: 10/10 activaciones locales; detección, entrega a proceso separado y contención loopback; no entrega remota ni revocación real |
| G4 | Evaluación final y adopción | Protocolo inicial; ejecución pendiente |

Esta arquitectura es deliberadamente mínima. Alta disponibilidad, multi-cloud, escalabilidad productiva y un catálogo general de Azure quedan fuera del trabajo.
