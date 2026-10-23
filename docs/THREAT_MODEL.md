# Modelo de amenazas

## Alcance y activos

El modelo cubre el flujo de desarrollo, GitHub Actions y el entorno Azure académico del caso PyroPrev. Los activos principales son credenciales, configuración, créditos estudiantiles, repositorios privados, identidad de despliegue, evidencia experimental y disponibilidad del trabajo académico.

No se modelan ataques de disponibilidad a escala productiva ni sistemas de terceros.

## Actores y supuestos

- Integrante legítimo que puede cometer un error al versionar configuración.
- Colaborador con acceso al repositorio que omite un control local.
- Atacante automatizado que obtiene un valor expuesto por un canal fuera del repositorio.
- Dependencia o acción de CI comprometida.
- Usuario del kit que ejecuta una prueba con una configuración incorrecta.

Se asume que GitHub y Azure autentican correctamente a sus usuarios. El acceso privado reduce exposición casual, pero no elimina errores internos, copias, logs, forks ni el uso automatizado de una credencial filtrada.

## Amenazas y controles

| ID | Amenaza | Consecuencia | Control principal | Evidencia/estado |
|---|---|---|---|---|
| T01 | Credencial agregada a un commit nuevo | Uso no autorizado y consumo de cuota | pre-commit + CI | G1 validado con secreto sintético |
| T02 | Credencial presente solo en historial Git | Persistencia aunque se borre del árbol | escaneo con historial completo | Piloto local y workflow implementados |
| T03 | Bypass o ausencia del hook local | Cambio inseguro llega al remoto | check CI requerido en `main` | Protección configurada |
| T04 | Reporte o log vuelve a exponer el valor | Amplificación de la fuga | redacción, permisos mínimos y retención breve | SARIF de CI-SEC-002 verificado |
| T05 | Binario o acción CI reemplazada | Ejecución de código no confiable | versiones, commits y SHA-256 fijados | Implementado en G1 |
| T06 | Secreto de cliente Azure almacenado en GitHub | Acceso Cloud persistente | OIDC y credenciales temporales | Login OIDC aprobado sin password, certificado o client secret |
| T07 | Identidad federada demasiado amplia | Despliegue desde repos o ramas no autorizadas | subject inmutable exacto, environment protegido y roles temporales a nivel de grupo | `AZ-LIFECYCLE-001`: dos roles temporales solo en el grupo, cero a nivel de suscripción y eliminación con el grupo |
| T08 | Configuración descifrada queda versionada | Exposición persistente | SOPS con `age`, `.gitignore`, hook por nombre/contenido, CI aislado y escaneo | Archivo sintético cifrado y descifrado local/CI validados; `.sops.yaml` integrado en la copia local PyroPrev, uso funcional pendiente |
| T09 | Perfil crea recursos costosos o residuales | Agotamiento de crédito estudiantil | preflight, `what-if`, escala a cero, una instancia máxima, etiquetas y destrucción | `AZ-LIFECYCLE-001`: residuo cero; `AZ-COST-001`: USD 0 usados y USD 100 restantes en la observación posterior |
| T10 | Honeytoken posee permisos útiles | La prueba causa impacto real | token aislado, sin privilegios y playbook | Pendiente G3 |
| T11 | Evidencia contiene datos atribuibles | Riesgo de confidencialidad | sanitización y resultados agregados | Regla vigente |
| T12 | Configuración compleja evita adopción | Equipos omiten todos los controles | kit acotado, defaults seguros y medición E5 | Diseño iniciado |

## Riesgos residuales relevantes

- Gitleaks puede producir falsos negativos y positivos; el piloto ya observó una omisión sintética que debe conservarse en la evaluación.
- Un administrador puede eludir la protección de rama configurada actualmente; este hecho debe quedar visible en la guía de adopción.
- El plan actual del repositorio privado no admitió revisores obligatorios para el entorno SOPS; el workflow manual y la restricción a ramas protegidas reducen, pero no eliminan, ese riesgo.
- Un secreto compartido fuera de Git no es prevenido por el scanner.
- OIDC reduce persistencia de credenciales, pero no corrige un rol excesivo ni un workflow mal autorizado.
- La acción `azure/login` registra el subject federado y metadatos del workflow;
  no son credenciales, pero los IDs inmutables de GitHub permanecen en logs privados.
- “Costo incremental cero” depende de oferta, región, cuota y fecha; no es una propiedad permanente de una plantilla.

## Criterios de revisión

Actualizar este modelo cuando se seleccione el perfil Azure, cambie una frontera de confianza, aparezca un hallazgo no cubierto o se modifiquen los permisos del pipeline. Cada control afirmado debe enlazarse con una prueba o declararse pendiente.
