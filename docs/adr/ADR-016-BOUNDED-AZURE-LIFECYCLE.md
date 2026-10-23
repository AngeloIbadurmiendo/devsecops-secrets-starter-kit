# ADR-016 - Ciclo Azure limitado a un grupo preexistente

**Estado:** implementado y validado en Cloud

**Fecha:** 13 de septiembre de 2026

## Contexto

La plantilla inicial tenía alcance de suscripción para crear su propio grupo de
recursos. Esa decisión obligaría a entregar permisos mutantes sobre toda la
suscripción a la identidad OIDC. Además, el módulo incluía roles de Storage que
no eran necesarios para la API HTTP mínima sin triggers.

## Decisión

1. Preparar el grupo de recursos y la confianza OIDC fuera del despliegue de la aplicación.
2. Ejecutar Bicep con alcance de grupo y exigir el nombre mediante configuración protegida.
3. Validar antes de cada operación ubicación y etiquetas de proyecto, entorno, propósito, responsable y expiración.
4. Exigir confirmaciones literales `apply:<proyecto>:<entorno>` y `destroy:<proyecto>:<entorno>`.
5. Conceder temporalmente `Contributor` y `Role Based Access Control Administrator` solo sobre el grupo durante la prueba mutante.
6. Mantener para la identidad de la Function `Storage Blob Data Owner` y `Storage Table Data Contributor`; no agregar permisos de bindings que el caso HTTP no utiliza.
7. Separar la destrucción del workflow de aplicación para permitir revisión humana y verificación externa de ausencia.

## Alternativas

### `Contributor` a nivel de suscripción

Rechazado. Facilita crear el grupo, pero permite cambiar recursos ajenos al
experimento y contradice el alcance mínimo.

### `Owner` sobre el grupo

Rechazado. Combina gestión de recursos y de acceso en un único rol más amplio.
La separación de roles hace explícita la razón por la que el despliegue necesita
crear asignaciones para la identidad de la Function.

### Conexiones Storage mediante claves

Rechazado. Simplificaría RBAC, pero reintroduciría secretos compartidos que el
framework busca evitar.

## Consecuencias

- El bootstrap debe crear y etiquetar el grupo antes de `plan --what-if` o `apply`.
- La identidad OIDC no puede modificar otros grupos por herencia de estos roles.
- `Role Based Access Control Administrator` puede delegar acceso dentro del grupo;
  se acepta solo temporalmente para la demostración y se elimina con el grupo.
- `destroy` elimina todo el grupo y requiere una identidad operadora capaz de
  comprobar después su ausencia.
- La evidencia `AZ-WHATIF-001` describe la plantilla anterior; la nueva variante
  requiere su propia compilación, `what-if` y ciclo mutante.

## Validación

`AZ-LIFECYCLE-001` demostró el 13 de septiembre de 2026 el ciclo completo. La
identidad OIDC usó exactamente los dos roles definidos sobre el grupo, el perfil
aprobó 11 comprobaciones y la destrucción dejó cero recursos Azure. El primer
intento fallido se atribuyó al verificador del framework y se preservó como
resultado negativo.

## Criterio de reversión

No aplicar si las etiquetas no coinciden, si los roles aparecen a un alcance
superior, si la cuota no permite FC1 o si Azure exige habilitar claves de Storage.

## Fuentes técnicas

- [Roles integrados de Azure](https://learn.microsoft.com/azure/role-based-access-control/built-in-roles)
- [Conexiones de Azure Functions mediante identidad](https://learn.microsoft.com/azure/azure-functions/manage-connections?tabs=identity)
- [Infraestructura como código para Azure Functions](https://learn.microsoft.com/azure/azure-functions/functions-infrastructure-as-code)
