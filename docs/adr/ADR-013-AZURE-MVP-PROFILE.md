# ADR-013 - Perfil Azure mínimo para G2

**Estado:** validado en Cloud; baseline PyroPrev integrado localmente y adaptación de aplicación pendiente

**Fecha:** 8 de septiembre de 2026

**Evidencia:** `AZ-PREFLIGHT-003` y `AZ-LIFECYCLE-001` (registros experimentales no incluidos en este repositorio)

## Contexto

G2 necesita demostrar infraestructura como código y autenticación GitHub-Azure mediante OIDC sin reconstruir toda la plataforma histórica de PyroPrev. La API disponible usa Flask y SQLAlchemy con conector MySQL, pero el aporte de la tesis es la prevención de fugas, la identidad efímera y la reproducibilidad, no la migración completa de la aplicación.

La suscripción evaluada es `Azure for Students`, mantiene el límite de gasto activado y no contiene recursos. El perfil debe ser pequeño, eliminable y compatible con una demostración controlada en pocas semanas.

## Decisión

El único perfil Cloud inicial será:

| Campo | Valor |
|---|---|
| Identificador | `functions-flex-python` |
| Región | `brazilsouth` |
| Cómputo | Azure Functions Flex Consumption (`FC1`) |
| Runtime | Azure Functions 4, Python 3.12 |
| Memoria por instancia | 512 MB |
| Máximo de instancias on-demand | 1 |
| Instancias always-ready | 0 |
| Despliegue | paquete de código, sin contenedor |
| Almacenamiento | cuenta Storage mínima `Standard_LRS`, requerida por Functions |
| Base de datos | `none` en el MVP |
| Telemetría | sin Log Analytics ni Application Insights en G2; reconsiderar solo para G3 |
| Identidad CI | OIDC de GitHub hacia una identidad Azure con alcance mínimo |
| Ciclo de vida | `plan -> apply -> verify -> destroy`, con confirmaciones explícitas |

El endpoint inicial será una ruta HTTP mínima derivada del fork de PyroPrev. La compatibilidad Flask se resolverá mediante el adaptador WSGI oficial de Azure Functions. No se afirmará que toda la API PyroPrev funciona hasta ejecutar su integración y pruebas correspondientes.

## Razones

1. Microsoft recomienda Flex Consumption para nuevas funciones serverless y publica soporte de Bicep para sus recursos requeridos.
2. La consulta de la suscripción listó `brazilsouth` entre 52 regiones Flex y como la única coincidencia sudamericana; `chilecentral` no apareció.
3. La consulta de runtime en `brazilsouth` confirmó Python 3.10 a 3.14. Se elige 3.12 por su soporte vigente y menor riesgo de compatibilidad que adoptar la versión más reciente sin necesidad.
4. 512 MB, una instancia máxima y cero always-ready limitan el consumo y permiten escala a cero. El objetivo es suficiencia experimental, no rendimiento productivo.
5. El perfil evita un registro de contenedores y reduce el número de recursos necesarios.
6. `database_profile=none` permite demostrar SOPS, OIDC, Bicep y despliegue sin convertir la base de datos histórica en una dependencia de G2.

## Alternativas consideradas

### Azure Container Apps

No seleccionada para el MVP. Mantendría la aplicación en un contenedor, pero agregaría construcción y distribución de imágenes, credenciales o identidad del registro y más decisiones de red que no responden directamente a las preguntas de investigación.

### App Service dedicado o Free

No seleccionado. Flex Consumption ofrece controles explícitos de escala a cero, memoria y máximo de instancias y es la opción serverless recomendada actualmente por Microsoft.

### Azure Database for MySQL Flexible Server

Diferida. Es coherente con el conector actual de PyroPrev, pero `az mysql flexible-server list-skus` devolvió `InternalServerError` en `brazilsouth`, `eastus2` y `southcentralus`. Además, la oferta gratuita documentada para MySQL depende de condiciones temporales y no es necesaria para demostrar el núcleo de G2. Podrá evaluarse como perfil opcional después del ciclo completo sin base de datos.

### Application Insights y Log Analytics desde G2

Diferidos para reducir proveedores, costo y retención de datos. G3 reevaluará la telemetría mínima necesaria para medir honeytokens; no se habilitará observabilidad por defecto sin un propósito experimental concreto.

## Consecuencias

- El kit puede abandonar los marcadores `pending-preflight` para región y cómputo.
- El futuro Bicep solo necesita inicialmente grupo de recursos, Storage, plan Flex, Function App e identidad/RBAC de despliegue.
- `Microsoft.Storage` se registró inmediatamente antes del primer despliegue.
- La ausencia de base de datos limita la demostración funcional a rutas que no dependan de persistencia. Esta limitación debe declararse en el caso de estudio.
- `AZ-COST-001` observó USD 0 usados y USD 100 restantes después del ciclo. Es evidencia del perfil y fecha ensayados, no una garantía permanente de costo cero.
- La cuota Flex específica no se pudo expresar como un valor concluyente antes del `apply`; la capacidad efectiva quedó demostrada por el despliegue FC1 exitoso. Esto no sustituye la medición posterior de consumo.

## Criterio de reversión

Cambiar el perfil solo si la validación o el primer despliegue controlado demuestra que Flex Consumption no está permitido en la suscripción, que Python 3.12 no ejecuta el adaptador de PyroPrev o que un recurso requerido incumple las guardas de costo. La alternativa debe conservar OIDC, Bicep, eliminación reproducible y alcance mínimo.

## Fuentes oficiales

- [Azure for Students](https://azure.microsoft.com/en-us/free/students/)
- [Flex Consumption plan](https://learn.microsoft.com/azure/azure-functions/flex-consumption-plan)
- [Infraestructura como código para Azure Functions](https://learn.microsoft.com/azure/azure-functions/functions-infrastructure-as-code)
- [Adaptador WSGI para Python](https://learn.microsoft.com/python/api/azure-functions/azure.functions.wsgimiddleware)
- [Autenticación OIDC desde GitHub Actions](https://learn.microsoft.com/azure/developer/github/connect-from-azure-openid-connect)
- [Azure Database for MySQL Flexible Server](https://learn.microsoft.com/azure/mysql/flexible-server/overview)
