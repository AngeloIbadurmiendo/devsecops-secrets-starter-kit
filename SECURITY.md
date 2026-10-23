# Política de seguridad del repositorio experimental

## Datos permitidos

- Credenciales completamente sintéticas y no válidas.
- Honeytokens creados específicamente para pruebas, aislados y sin privilegios.
- Resultados de herramientas después de eliminar valores sensibles.
- Metadatos de repositorios necesarios para reproducibilidad.
- Datos de participantes anonimizados y con el tratamiento aprobado.

## Datos prohibidos

- Claves API, tokens, contraseñas o cadenas de conexión reales.
- Credenciales revocadas reproducidas en texto completo.
- Archivos `.env`, `local.properties` u otros archivos históricos copiados desde PyroPrev.
- Identificadores personales, correos o respuestas atribuibles a participantes.
- IDs de suscripciones, tenants o aplicaciones Cloud salvo que sean estrictamente necesarios y estén en almacenamiento privado separado.

## Respuesta ante una inclusión accidental

1. Detener el trabajo y no copiar el valor a issues, logs o mensajes.
2. Revocar o rotar la credencial desde el proveedor correspondiente.
3. Preservar únicamente evidencia sanitizada del incidente.
4. Eliminar el valor del estado actual y del historial antes de publicar o compartir el repositorio.
5. Registrar el incidente sin incluir el secreto.
6. Verificar nuevamente el historial con más de un control cuando sea necesario.

## Regla del corpus

Todo caso positivo debe incluir un manifiesto que indique que el valor es sintético. La apariencia de realismo se obtiene conservando la estructura del formato, no reutilizando material secreto.

