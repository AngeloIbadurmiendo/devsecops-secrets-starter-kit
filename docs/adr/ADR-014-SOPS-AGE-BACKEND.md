# ADR-014 - Usar age como backend inicial de SOPS

## Estado

Aceptada y validada con una identidad local y otra exclusiva de CI; administración de seis integrantes y respaldo externo pendientes.

## Contexto

La propuesta exige configuración cifrada y versionable. El mecanismo debe funcionar sin licencias, no introducir credenciales Cloud permanentes y ser suficientemente simple para equipos académicos. SOPS cifra los valores de documentos estructurados, pero requiere uno o más mecanismos externos que protejan la clave de datos.

## Decisión

El backend inicial será `age` con las siguientes reglas:

- cada persona o proceso autorizado utiliza un par de claves independiente;
- solo los destinatarios públicos `age1...` pueden ingresar a `.sops.yaml`;
- las claves privadas permanecen fuera del repositorio y de sus logs;
- los archivos descifrados utilizan nombres excluidos por Git y existen el menor tiempo posible;
- CI tiene un destinatario separado y revocable, almacenado como secreto del entorno GitHub `sops-demo`;
- la demostración local genera clave y valores sintéticos en un directorio efímero y conserva únicamente métricas y hashes sanitizados.

La demostración crea una clave local persistente fuera del checkout y una clave separada para CI. Solo sus destinatarios públicos y un archivo sintético cifrado se versionan. La incorporación de configuración al fork PyroPrev se realizará después de respaldar de forma durable la identidad local y congelar los destinatarios aplicables al caso.

El kit 0.3.0 implementa esta decisión mediante destinatarios públicos validados, generación condicional de `.sops.yaml` y un hook que rechaza archivos descifrados o material de clave privada. `SOPS-CONFIG-001` conserva esa validación y `SOPS-CI-001` demuestra que ambas identidades independientes pueden recuperar el mismo documento sintético sin filtrar valores en logs o artefactos.

## Alternativas consideradas

### Azure Key Vault

Permite centralizar el control y aprovechar identidad Azure, pero acopla el descifrado local a una sesión Cloud, requiere recursos y permisos antes de completar la prueba local y aumenta la fricción para adopción académica.

### PGP

Es compatible con SOPS, pero la administración de llaves y confianza resulta más amplia que lo necesario para este caso.

### Clave age compartida por todo el equipo

Reduce la configuración inicial, pero impide atribución individual y obliga a rotar para todos cuando una persona deja el proyecto. Se rechaza como patrón recomendado.

## Consecuencias

- El repositorio puede incluir configuración cifrada sin conservar el texto claro.
- La pérdida de una clave privada exige que exista otro destinatario o un procedimiento de recuperación.
- Agregar o retirar integrantes requiere actualizar destinatarios y rotar el archivo con SOPS.
- La clave de CI seguirá siendo material sensible aunque no sea una credencial Azure; deberá quedar fuera de Git y tener alcance propio.
- OIDC continúa resolviendo por separado la autenticación efímera GitHub-Azure.

## Criterio de reversión

Se reconsiderará `age` si la prueba de adopción evidencia recuperación inviable, si el equipo docente exige administración centralizada o si la integración CI obliga a mantener un secreto con riesgo mayor al beneficio observado.

## Evidencia

- Registros experimentales `SOPS-LOCAL-001`, `SOPS-CONFIG-001` y `SOPS-CI-001` (no incluidos en este repositorio)
- `scripts/run_sops_age_demo.py`
- `.github/workflows/sops-ci-demo.yml`
