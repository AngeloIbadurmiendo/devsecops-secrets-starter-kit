# ADR-015 - Bootstrap OIDC separado del despliegue

**Estado:** login y autorización de despliegue acotada validados

**Fecha:** 11 de septiembre de 2026

## Contexto

G2 debe demostrar autenticación GitHub-Azure sin un secreto permanente y con
alcance mínimo. Otorgar permisos de despliegue antes de comprobar issuer, audience
y subject mezclaría autenticación y autorización, dificultando atribuir un fallo.

El repositorio fue creado después del cambio de GitHub del 15 de julio de 2026 y
usa el sujeto OIDC inmutable predeterminado, que incorpora IDs del propietario y
repositorio. Estos valores son necesarios en la confianza de Azure, pero no en la
evidencia académica.

## Decisión

1. Crear una identidad administrada asignada por usuario dentro del grupo experimental.
2. Crear una única credencial federada para el environment `azure-demo`.
3. Restringir el environment a ramas protegidas.
4. Crear el grupo objetivo vacío y etiquetado que utilizará el perfil G2.
5. Asignar inicialmente solo `Reader` a ese grupo.
6. Ejecutar un workflow manual que autentique y pruebe visibilidad del grupo.
7. Evaluar permisos de despliegue en un incremento posterior y con autorización separada.

## Alternativas

### Secreto de cliente

Rechazado. Es precisamente la credencial permanente que el objetivo busca evitar.

### Rol Contributor de suscripción desde el inicio

Rechazado. Permitiría modificar recursos fuera del experimento y no es necesario
para demostrar autenticación.

### Aplicación Microsoft Entra

Fue la primera alternativa intentada, pero Azure rechazó `az ad app create` porque
la cuenta estudiantil no posee permiso de directorio para registrar aplicaciones.
El intento no creó una aplicación residual. La identidad administrada permite la
misma federación mediante ARM y queda contenida en el grupo eliminable.

### Confianza por rama sin environment

No seleccionada. El environment permite una frontera explícita y reglas de
despliegue. Se reconoce que los revisores obligatorios no están disponibles para
este repositorio privado bajo el plan actual.

## Consecuencias

- El primer resultado OIDC solo prueba autenticación temporal y lectura acotada;
  `AZ-LIFECYCLE-001` aporta la prueba mutante separada.
- El grupo y la identidad administrada se eliminaron al terminar el ciclo.
- Client, tenant y subscription IDs permanecen fuera de Git y de la evidencia.
- Un permiso futuro deberá medirse contra la operación concreta; no se promoverá
  automáticamente `Reader` a un rol más amplio.

## Criterio de reversión

Eliminar credencial federada, asignación RBAC, identidad administrada y grupo si el subject
inmutable no coincide, el plan de GitHub no permite restringir el environment o
Azure exige una credencial permanente.

## Validación observada

`OIDC-LOGIN-001` ejecutó el workflow sobre el commit `9a6a11b`. GitHub obtuvo un
token temporal, Azure lo aceptó y la identidad pudo leer el grupo objetivo. El job
duró 15 segundos. No existían Function Apps ni Storage y no se otorgaron permisos
mutantes.

`AZ-LIFECYCLE-001` promovió temporalmente la misma identidad a `Contributor` y
`Role Based Access Control Administrator` solo sobre el grupo. El ciclo completo
fue exitoso y la eliminación posterior dejó cero recursos e identidades Azure.
Los valores obsoletos del environment también fueron retirados.

La acción `azure/login` 3.1.0 imprime issuer, subject, audience y
`job_workflow_ref` como información de diagnóstico. No imprimió token, client ID,
tenant ID ni subscription ID, pero el subject contiene IDs inmutables de GitHub.
Por tanto, la evidencia sanitizada no afirma que el log esté libre de todo
identificador; conserva esta limitación de proveedor.
