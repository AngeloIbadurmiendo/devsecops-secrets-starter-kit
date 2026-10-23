# Registro inicial de decisiones técnicas

Las decisiones permanecen provisionales hasta completar el ADR correspondiente o recibir validación académica.

| ID | Decisión provisional | Estado | Razón inicial |
|---|---|---|---|
| ADR-001 | Gitleaks como scanner principal | Piloto en evaluación | Código abierto; el piloto valida árbol, staged e historial y registra una omisión AWS inicial |
| ADR-002 | `pre-commit` como integrador local | Propuesta | Instalación conocida y configuración versionable |
| ADR-003 | GitHub Actions como plataforma CI/CD | Confirmada | Plataforma usada por el equipo y disponible para la Feria |
| ADR-004 | SOPS para configuración cifrada | Confirmada por propuesta | Permite almacenar configuración cifrada y auditable |
| ADR-005 | OIDC GitHub-Azure | Confirmada por propuesta | Elimina el secreto de cliente Cloud permanente |
| ADR-006 | Bicep como IaC principal | Implementación estática validada | El perfil único compila sin advertencias, se genera de forma determinística y todavía no ha sido aplicado |
| ADR-007 | Python estándar para scripts de soporte | Propuesta | Portabilidad y disponibilidad en runners sin dependencias iniciales |
| ADR-008 | Descargar Gitleaks fijado y verificar su SHA-256 en CI | Implementada | Evita depender de una acción con condiciones de licencia distintas y asegura la integridad del binario ejecutado |
| ADR-009 | Publicar solo SARIF redactado con retención breve | Implementada | Conserva evidencia útil reduciendo exposición de valores y permanencia de metadatos sensibles |
| ADR-010 | Usar Azure CLI/Bicep como motor del ciclo y un wrapper delgado en Python | Validada con ajuste | `doctor/init/generate/plan/apply/verify/destroy` funcionan; el ciclo Cloud real quedó registrado en `AZ-LIFECYCLE-001` |
| ADR-011 | Validar primero un solo perfil Azure y como máximo dos opciones de base de datos | Aceptada para implementar | Mantiene el artefacto verificable dentro del plazo y evita prometer combinaciones no probadas |
| ADR-012 | Tratar el kit como artefacto de adopción del framework | Implementada en el diseño | Aporta transferencia práctica y métricas de facilidad de adopción sin cambiar el objetivo ni las preguntas de investigación |
| ADR-013 | Usar Azure Functions Flex Consumption con Python 3.12 en `brazilsouth`, 512 MB, una instancia máxima, cero always-ready y sin base de datos en G2 | Validada en Cloud | El perfil fue desplegado, verificó 11 controles y fue destruido sin residuo; integración Flask pendiente |
| ADR-014 | Usar destinatarios `age` individuales como backend inicial de SOPS | Recuperación local/CI y configuración local PyroPrev demostradas | Es gratuito y portable; falta probar la restauración del respaldo y el uso funcional de configuración cifrada en el caso |
| ADR-015 | Separar el bootstrap OIDC del permiso de despliegue | Login y despliegue validados | La identidad administrada pasó temporalmente de `Reader` a dos roles de grupo, ejecutó el ciclo y fue eliminada con el grupo |
| ADR-016 | Limitar el ciclo mutante a un grupo preexistente y etiquetado | Validada en Cloud | Evitó permisos de suscripción, exigió confirmaciones literales y separó aplicación de destrucción |

Cada ADR final debe incluir contexto, alternativas, consecuencias, criterio de reversión y evidencia.
