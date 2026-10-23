# GitHub Actions y Azure OIDC

## Propósito

El framework usa federación de carga de trabajo para que GitHub Actions obtenga
un token Azure temporal. No se crea ni almacena un secreto de cliente.

La demostración inicial separó autenticación de despliegue: una identidad
administrada asignada por usuario recibió `Reader` sobre un grupo vacío y el
workflow manual comprobó que podía verlo. La prueba mutante posterior usó
temporalmente `Contributor` y `Role Based Access Control Administrator` solo en
el grupo, porque la plantilla administra recursos y crea dos asignaciones de datos.

## Frontera de confianza

- Emisor: `https://token.actions.githubusercontent.com`.
- Audiencia Azure pública: `api://AzureADTokenExchange`.
- Repositorio: el repositorio privado del framework.
- Sujeto: environment `azure-demo`, usando el formato inmutable predeterminado
  de GitHub para repositorios creados después del 15 de julio de 2026.
- Alcance RBAC: `Reader` para el login inicial y dos roles temporales de despliegue
  sobre el mismo grupo durante el ciclo mutante.

Los IDs inmutables necesarios para construir el sujeto y los identificadores de
Azure no se versionan. Se almacenan solo en la configuración privada de Azure y
como secretos del environment de GitHub, siguiendo la recomendación del proveedor.

## Workflow de demostración

`.github/workflows/oidc-login-demo.yml` cumple estas restricciones:

- solo `workflow_dispatch`;
- environment `azure-demo`;
- permiso `id-token: write` limitado al job;
- permiso de repositorio `contents: read`;
- `azure/login` fijado al commit correspondiente a v3.1.0;
- ningún checkout ni ejecución de código del repositorio;
- validación de tenant, suscripción, tipo de principal y grupo esperado sin imprimir IDs;
- artefacto con métricas sanitizadas y cierre de sesión bajo `if: always()`.

`OIDC-LOGIN-001` validó el flujo: Azure aceptó el token, el principal se identificó
como `servicePrincipal` y pudo leer el grupo objetivo en un job de 15 segundos.
No se crearon Function Apps ni Storage y el rol siguió siendo `Reader`.

## Configuración privada esperada

El environment contiene tres secretos de configuración, no credenciales de larga
duración:

- `AZURE_CLIENT_ID`;
- `AZURE_TENANT_ID`;
- `AZURE_SUBSCRIPTION_ID`.

La variable `AZURE_RESOURCE_GROUP` contiene el nombre del alcance experimental.
El workflow no acepta un `client-secret`. Tras `AZ-LIFECYCLE-001`, los cuatro
valores obsoletos se eliminaron y el environment protegido quedó disponible para
un futuro bootstrap.

## Rotación y eliminación

La confianza puede revocarse eliminando la credencial federada o la identidad
administrada. El rol se elimina de manera independiente. Al terminar el experimento
deben eliminarse la asignación RBAC, el grupo experimental, la identidad y los
valores del environment, registrando solo conteos sanitizados. Este cierre fue
demostrado en `AZ-LIFECYCLE-001`.

## Limitaciones

- El environment privado actual no permite exigir revisores bajo el plan disponible.
- Cualquier workflow autorizado que use el mismo environment puede solicitar un
  token; por eso se restringe el environment a ramas protegidas.
- `id-token: write` permite solicitar un token OIDC, pero no otorga por sí mismo
  permisos Azure; la autorización efectiva depende de RBAC.
- El login aislado no demuestra capacidad de desplegar ni privilegio mínimo para
  una operación futura distinta; el ciclo mutante solo demuestra el perfil FC1
  ensayado.
- `azure/login` 3.1.0 escribe issuer, subject, audience y `job_workflow_ref` en el
  log. No se observaron token ni IDs Azure configurados, pero el subject conserva
  IDs inmutables de GitHub; el artefacto académico no los replica.
- El intento inicial de crear una aplicación Entra falló por falta de permiso de
  directorio y no dejó residuos; la identidad administrada fue la alternativa
  funcional bajo las capacidades reales de la cuenta estudiantil.

## Fuentes oficiales

- [Azure Login con OpenID Connect](https://learn.microsoft.com/azure/developer/github/connect-from-azure-openid-connect)
- [Configurar OIDC en Azure](https://docs.github.com/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure)
- [Referencia de claims OIDC](https://docs.github.com/actions/reference/security/oidc)
