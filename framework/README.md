# Componentes del framework

Esta carpeta contiene los componentes reutilizables e independientes de PyroPrev.
La [guía de uso para equipos](../README.md) está en la portada del repositorio.

Orden de implementación:

1. configuración de pre-commit;
2. configuración del scanner;
3. workflow reutilizable;
4. integración SOPS;
5. módulo de alerta y respuesta.

## Kit de inicio

El primer incremento local se ejecuta como módulo Python:

```powershell
python -m framework.starter_kit doctor --mode local
python -m framework.starter_kit init --name proyecto-feria --non-interactive
python -m framework.starter_kit generate --output ./generated-project
```

`doctor`, `init` y `generate` no cambian recursos remotos. La versión 0.7.4
genera código de ejemplo en `app/` y pruebas, separados del runtime `framework/`;
los demos Azure quedan inactivos en `examples/`. El perfil actual fija
`functions-flex-python` en `brazilsouth` y base de datos `none`; para compilar
un plan local se requiere además Azure CLI con Bicep. El ejemplo abreviado de
arriba no sustituye la guía de la raíz ni configura una suscripción.

Los adaptadores específicos del caso de estudio deben quedar fuera de este directorio.
