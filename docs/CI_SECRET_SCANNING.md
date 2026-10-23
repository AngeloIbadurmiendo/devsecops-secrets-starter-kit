# Detección de secretos en GitHub Actions

## Objetivo

El control de CI complementa el hook local. Su función es impedir que un bypass, una instalación incompleta o un secreto presente únicamente en el historial pase inadvertido antes de integrar cambios.

## Artefactos

- `.github/workflows/reusable-secret-scan.yml`: implementación reutilizable.
- `.github/workflows/secret-scan.yml`: activación en `push`, `pull_request` y ejecución manual.
- `.gitleaks.toml`: configuración común con el control local.

## Garantías de diseño

- Gitleaks está fijado en la versión 8.30.1.
- El binario Linux se valida con el SHA-256 publicado para esa versión.
- El checkout obtiene el historial completo y no conserva credenciales Git.
- El token automático solo recibe `contents: read`.
- El workflow no recibe ni hereda secretos.
- El informe SARIF se genera con valores redactados y se conserva 14 días por defecto junto con métricas JSON sanitizadas.
- Un hallazgo produce un fallo del job después de publicar la evidencia sanitizada.
- La duración del escaneo y el número de hallazgos quedan disponibles como outputs y en `gitleaks-metrics.json`.

## Uso en el mismo repositorio

El archivo `secret-scan.yml` ya llama al workflow reutilizable:

```yaml
jobs:
  gitleaks:
    permissions:
      contents: read
    uses: ./.github/workflows/reusable-secret-scan.yml
```

## Uso desde otro repositorio

Cuando el framework tenga un repositorio remoto accesible, el consumidor debe llamar una versión inmutable, preferentemente un commit SHA:

```yaml
jobs:
  gitleaks:
    permissions:
      contents: read
    uses: PROPIETARIO/framework-devsecops/.github/workflows/reusable-secret-scan.yml@COMMIT_SHA
```

No se utiliza `secrets: inherit`. En repositorios privados, el propietario del framework deberá habilitar explícitamente el acceso desde los repositorios consumidores.

## Interpretación

- Código `0`: no se encontraron secretos.
- Código `1`: existe al menos un hallazgo; el job falla y conserva el SARIF redactado.
- Otro código o salida ausente: error de ejecución; el job falla sin confundirlo con un repositorio limpio.

El reporte puede incluir rutas, reglas y metadatos de commits. Aunque los valores estén redactados, debe tratarse como evidencia privada y sanitizarse de nuevo antes de publicarlo fuera del equipo. El archivo de métricas no contiene valores detectados ni rutas de archivos.

## Protección de rama

Después de validar el workflow en GitHub, se recomienda configurar el job `Gitleaks` como comprobación obligatoria antes de merge. Esa configuración es externa al repositorio y debe registrarse por separado.
