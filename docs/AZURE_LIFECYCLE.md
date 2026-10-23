# Ciclo Azure del perfil mínimo

## Alcance

El kit 0.7.2 implementa `plan`, `apply`, `verify` y `destroy` para un grupo ya
creado y etiquetado. `AZ-LIFECYCLE-001` demuestra el ciclo real completo y su
destrucción sin residuo Azure.

El grupo debe tener exactamente estas propiedades coherentes con
`feria-project.json`:

- ubicación `brazilsouth`;
- `managedBy=feria-starter`;
- `purpose=academic-devsecops-validation`;
- `projectName=<proyecto>`;
- `environment=<entorno>`;
- `expiresOn=<fecha futura>`.

## Permisos de despliegue

El workflow usa la misma confianza OIDC de `azure-demo`. Para el ciclo mutante la
identidad necesita temporalmente, solo en el grupo objetivo:

- `Contributor`, para administrar los recursos declarados;
- `Role Based Access Control Administrator`, porque Bicep crea los dos roles de
  datos de la identidad usada por la Function.

`Contributor` por sí solo no puede crear asignaciones RBAC. No se concede
`Owner`, no se utiliza alcance de suscripción y los permisos desaparecen al
eliminar el grupo.

## Comandos

```powershell
python -m framework.starter_kit plan `
  --config feria-project.json `
  --template infra/bicep/main.bicep `
  --resource-group <grupo-preparado> `
  --what-if `
  --output .feria/plan.json

python -m framework.starter_kit apply `
  --config feria-project.json `
  --template infra/bicep/main.bicep `
  --resource-group <grupo-preparado> `
  --confirm apply:<proyecto>:<entorno> `
  --output .feria/apply.json

python -m framework.starter_kit verify `
  --config feria-project.json `
  --resource-group <grupo-preparado> `
  --output .feria/verify.json

python -m framework.starter_kit destroy `
  --config feria-project.json `
  --resource-group <grupo-preparado> `
  --confirm destroy:<proyecto>:<entorno> `
  --output .feria/destroy.json
```

Los resultados conservan estados, comprobaciones y conteos por tipo. No conservan
nombres de recursos, IDs Azure, tokens, valores de configuración ni respuestas
ARM completas.

## Verificación

`verify` exige un único Storage, plan FC1 y Function App; Python 3.12, HTTPS,
máximo una instancia, acceso público Blob y claves compartidas deshabilitados,
configuración `AzureWebJobsStorage` basada en identidad, ausencia de base de datos
y ausencia de telemetría.

La identidad de la Function recibe `Storage Blob Data Owner`, mínimo documentado
para el almacenamiento requerido por el host, y `Storage Table Data Contributor`
para sus eventos diagnósticos. No se agregan permisos de Queue o bindings porque
la demostración no los utiliza.

## Destrucción

`destroy` vuelve a validar todas las etiquetas, exige confirmación literal,
elimina el grupo completo y comprueba que Azure responda `false` a `group
exists`. El workflow de aplicación no llama este comando automáticamente: la
destrucción se ejecuta y registra como paso separado.

## Evidencia ejecutada

El 13 de septiembre de 2026 el workflow OIDC aplicó el perfil y aprobó 11 de 11
comprobaciones. Un primer intento reveló dos incompatibilidades del verificador
con Azure CLI/ARM; se registró como resultado negativo, se corrigió con pruebas y
la segunda ejecución fue exitosa. La comprobación posterior a `destroy` observó
cero grupos, recursos e identidades administradas en la suscripción. El registro `AZ-LIFECYCLE-001` no se incluye en este repositorio.

La observación posterior `AZ-COST-001` registró USD 0 usados y USD 100 de crédito
restante. Este resultado se limita al ciclo y fecha observados; no garantiza que
otras cargas o futuras condiciones de Azure mantengan el mismo costo.
