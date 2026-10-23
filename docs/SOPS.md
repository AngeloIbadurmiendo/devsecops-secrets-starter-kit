# Configuración cifrada con SOPS y age

## Propósito

El framework utiliza SOPS para versionar configuración sensible cifrada y `age` para proteger la clave de datos. Este control no sustituye un almacén de secretos en tiempo de ejecución ni autoriza almacenar credenciales reales en el repositorio.

La decisión y sus alternativas se encuentran en [ADR-014](adr/ADR-014-SOPS-AGE-BACKEND.md).

## Modelo de claves

- Cada integrante autorizado genera su propio par `age`.
- La clave privada nunca se copia al repositorio, issues, logs o mensajería del equipo.
- El destinatario público con prefijo `age1` puede incluirse en `.sops.yaml`.
- CI utiliza un destinatario diferente de los integrantes.
- Deben existir al menos dos vías de recuperación antes de depender de un archivo cifrado real.

La demostración versionada utiliza dos identidades independientes: una clave del propietario conservada fuera del checkout y una clave exclusiva del entorno GitHub `sops-demo`. Ambas pudieron descifrar el mismo archivo sintético. [SOPS-RESTORE-001](../evidence/sops/SOPS-RESTORE-001.md) verificó la copia declarada transcrita desde papel contra los fixtures sintéticos del framework y del caso, con descubrimiento de identidades aislado y controles negativos antes/después. La custodia física y un desastre real no fueron evaluados.

Una clave se genera fuera del repositorio:

```powershell
$keyDirectory = Join-Path $env:APPDATA 'sops\age'
New-Item -ItemType Directory -Force -Path $keyDirectory
age-keygen -o (Join-Path $keyDirectory 'keys.txt')
age-keygen -y (Join-Path $keyDirectory 'keys.txt')
```

El segundo comando imprime únicamente el destinatario público. La ubicación puede cambiar, pero debe permanecer fuera del checkout y contar con un respaldo seguro definido por el propietario. No se recomienda compartir una sola clave privada entre seis integrantes.

## Configuración del repositorio

Una futura configuración real tendrá esta forma, reemplazando los ejemplos solo por destinatarios públicos:

```yaml
creation_rules:
  - path_regex: '(^|.*[\\/])secrets\.enc\.(yaml|yml|json)$'
    age: >-
      age1DESTINATARIO_PUBLICO_INTEGRANTE,
      age1DESTINATARIO_PUBLICO_CI
```

El archivo claro debe usar un nombre excluido por Git, por ejemplo `secrets.sops-dec.yaml`. El archivo versionable usa `secrets.enc.yaml`.

El kit recibe uno o más destinatarios públicos repetibles. Si no se entrega ninguno, omite `.sops.yaml` en vez de generar una configuración incompleta:

```powershell
python -m framework.starter_kit init `
  --name ejemplo-feria `
  --sops-age-recipient age1DESTINATARIO_PUBLICO `
  --non-interactive
python -m framework.starter_kit generate `
  --config feria-project.json `
  --output .
```

El kit valida estructura y checksum Bech32, rechaza duplicados y limita el perfil inicial a ocho destinatarios: aproximadamente seis integrantes, CI y una identidad de recuperación.

## Flujo previsto

1. Crear o editar el archivo claro fuera del staging area.
2. Cifrarlo con SOPS aplicando los destinatarios públicos declarados:

   ```powershell
   sops --config .sops.yaml encrypt `
     --filename-override secrets.enc.yaml `
     --output secrets.enc.yaml `
     secrets.sops-dec.yaml
   ```

   `--filename-override` permite que SOPS seleccione la regla del archivo cifrado aunque la entrada tenga el nombre seguro reservado para texto claro.

3. Verificar que los valores no aparecen en el archivo cifrado.
4. Eliminar el archivo claro y comprobar `git status`.
5. Ejecutar Gitleaks antes de crear el commit.
6. En CI, materializar la clave del destinatario de automatización solo durante el job y eliminarla al finalizar.

Además de `.gitignore`, el hook local `forbid-plaintext-secret-files` rechaza nombres `.env`, `local.properties`, `secrets.plain.*`, `*.decrypted.*` y `*.sops-dec.*`. También inspecciona contenido para bloquear material privado age aunque el archivo tenga un nombre inocuo. No sustituye Gitleaks ni evita que un usuario omita todos los hooks; GitHub Actions sigue siendo la segunda barrera.

## Demostración en GitHub Actions

El workflow manual `.github/workflows/sops-ci-demo.yml` ejecuta una prueba exclusivamente sintética:

1. obtiene SOPS 3.13.3 y verifica el SHA-256 oficial del binario;
2. materializa `SOPS_AGE_KEY` desde el entorno GitHub `sops-demo` en un archivo temporal con permisos restrictivos;
3. descifra `examples/sops/secrets.enc.json` sin enviar el contenido a stdout;
4. compara un hash semántico esperado y comprueba que el ciphertext no contiene valores claros ni material privado;
5. publica únicamente métricas sanitizadas;
6. elimina la clave y el documento claro incluso si un paso anterior falla.

El entorno solo admite ramas protegidas. GitHub rechazó la regla adicional de revisores obligatorios para el plan actual del repositorio privado, por lo que el control compensatorio es un trigger exclusivamente manual, permisos `contents: read`, un archivo sintético y una clave de CI sin otro uso. Esta limitación debe reevaluarse antes de aplicar el patrón a secretos de una aplicación.

Los registros experimentales `SOPS-CI-001` y `SOPS-PYRO-LOCAL-001` (no incluidos en este repositorio) demostraron el ciclo autorizado en CI y el consumo funcional sintético en una Flask mínima: firma de sesión y rechazo de alteraciones, sin texto claro en disco. No demuestran una API histórica, rotación desde CI ni restauración del respaldo físico. El caso usa una identidad local; la prueba de dos identidades anterior pertenece al fixture del framework.

## Incorporación y retiro de integrantes

- **Incorporación:** agregar el destinatario público, rotar las claves de datos con SOPS y revisar el diff cifrado.
- **Retiro:** eliminar su destinatario, rotar las claves de datos y reemplazar cualquier secreto de aplicación que la persona hubiera conocido.
- **Pérdida de clave:** utilizar otro destinatario autorizado para descifrar y volver a cifrar; si no existe, el contenido no es recuperable. El fixture del framework conserva dos destinatarios; la copia física transcrita recuperó los fixtures sintéticos en SOPS-RESTORE-001, no secretos de aplicación. El caso conserva un destinatario local.

El cambio de destinatarios debe pasar por pull request y nunca debe incluir claves privadas.

## Demostración segura

Desde el repositorio técnico:

```powershell
python scripts/run_sops_age_demo.py
```

La prueba crea una clave efímera y dos valores sintéticos, comprueba el ciclo de cifrado y descifrado y elimina los archivos temporales. Solo conserva métricas, hashes y aserciones sanitizadas en [SOPS-LOCAL-001](../evidence/sops/SOPS-LOCAL-001.md).
