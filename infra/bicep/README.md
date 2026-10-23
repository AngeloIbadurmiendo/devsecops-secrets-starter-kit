# Infraestructura Azure

La infraestructura de G2 está expresada como Bicep con alcance de grupo. Puede
compilarse sin crear recursos y su aplicación exige autorización y confirmación explícitas.

Principios:

- despliegue mínimo necesario para demostrar OIDC y el caso de estudio;
- privilegio mínimo;
- etiquetas de proyecto, entorno y propietario;
- presupuesto y alertas antes de cargas relevantes;
- creación y eliminación reproducibles;
- ninguna dependencia de Pay-As-You-Go.

No agregar IDs personales, secretos ni parámetros descifrados a este directorio.

## Perfil seleccionado

`ADR-013` fija como único candidato inicial `functions-flex-python`:

- región `brazilsouth`;
- Azure Functions Flex Consumption, runtime 4 y Python 3.12;
- 512 MB, máximo una instancia on-demand y cero always-ready;
- Storage `Standard_LRS` requerido por Functions;
- sin base de datos, Application Insights ni Log Analytics en G2.

La selección no equivale a un despliegue validado. Los módulos Bicep deberán exponer `what-if`, etiquetado, fecha de expiración y destrucción, y no se aplicarán sin autorización explícita.

## Validación local

```powershell
az bicep build --file infra/bicep/main.bicep --stdout | Out-Null
```

La plantilla se aplica a un grupo preexistente y etiquetado. Dentro de él propone
Storage, una identidad administrada, dos asignaciones RBAC, un plan FC1 y una
Function App. No incluye base de datos ni telemetría. La configuración fija
512 MB, máximo una instancia on-demand y cero instancias always-ready (valor por
omisión al no declararlas).

El máximo de una instancia es una guarda experimental de consumo, no una
recomendación de producción: una carga HTTP con ráfagas puede sufrir throttling.

El kit genera `main.bicepparam` desde `feria-project.json`. Un valor
`expires_on=pending` es válido para `generate`, pero `plan` lo rechaza antes de
compilar o consultar Azure.

```powershell
python -m framework.starter_kit plan `
  --config <proyecto>/feria-project.json `
  --output <proyecto>/.feria/plan.json

python -m framework.starter_kit plan `
  --config <proyecto>/feria-project.json `
  --resource-group <grupo-preparado> `
  --output <proyecto>/.feria/what-if-plan.json `
  --what-if
```

La salida ARM completa no se conserva porque contiene IDs de la cuenta. El plan
sanitizado registra únicamente conteos por tipo de cambio. El experimento
`AZ-WHATIF-001` confirmó doce creaciones para la variante inicial de alcance de
suscripción. La variante de grupo incorporada en 0.7.0 requiere nueva evidencia
antes de aplicar.
