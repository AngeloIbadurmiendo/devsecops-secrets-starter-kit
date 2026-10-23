# Honeytoken local y playbook — piloto G3

## Decisión y límites

Primera implementación: credencial señuelo sintética para un receptor HTTP
exclusivamente 127.0.0.1, puerto efímero. No representa una clave Azure/Gemini/R2,
no accede a datos ni permite gastar créditos. No se distribuye ni versiona su
valor; solo vive en RAM durante el piloto. No se garantiza borrado físico de RAM.
Un uso coincidente encola detección; otro thread registra alerta local e invalida
el señuelo. Reutilizarlo obtiene 410. Un valor desconocido obtiene 404 sin alerta.

La alerta es un evento en memoria, conservado luego en el reporte: no es correo,
webhook externo ni lectura por un operador. La contención es invalidación del
señuelo en el laboratorio, no revocación en un proveedor real. Por tanto, los
tiempos no deben etiquetarse como Time-to-Revoke Azure ni tiempo de respuesta
humana. G3 integral y evaluación final permanecen abiertos.

La [documentación oficial de Canarytokens HTTP](https://docs.canarytokens.org/guide/http-token.html)
explica la activación de un señuelo mediante solicitud HTTP. Este piloto es una
implementación local acotada del concepto, no usa ni integra ese servicio.
[NIST SP 800-61r3](https://csrc.nist.gov/pubs/sp/800/61/r3/final) fundamenta organizar
preparación, detección y respuesta; no certifica esta implementación.

## Procedimiento del piloto fijado antes de medir

Una ejecución, distinta del lote E4 final de diez repeticiones. Se comprueban
tres solicitudes reales a loopback: desconocida 404 sin alerta, activación 204,
replay 410 tras contención. No se hacen peticiones externas, DNS, proxies,
redirecciones, cargas ni instalaciones. Se registran detección, alerta local e
invalidación con UTC y diferencias perf_counter_ns dentro del mismo proceso.
Activación inicia inmediatamente antes de enviar la solicitud válida; alerta
es recepción por el monitor y contención es cambio de estado. No comparar esos
tiempos locales con logs de otro reloj. No se descartan fallos por ser negativos.
El script reserva un archivo nuevo antes de abrir sockets y no sobrescribe.

Desde el repositorio del framework, con worktree limpio y directorio existente:

```powershell
python scripts/run_honeytoken_pilot.py --output ../tmp/HONEY-LOCAL-001-20260915.json
```

La salida inicial debe estar fuera del repositorio y no existir. Reservarla
dentro del repositorio crearía un untracked antes de registrar el estado Git.
Después de ejecutar, copiar el JSON generado a un directorio de evidencia propio, sin
alterar sus valores. Para otra ejecución usar un nombre nuevo y autorización.

Los tests también activan un señuelo efímero: son regresiones, no observaciones
del dataset final. El receptor y los threads se cierran antes de devolver resultado.
Headers y solicitudes no se imprimen; reportes no contienen valor, URL o cliente.

## Playbook para el laboratorio

1. Preparar autorización, commit, salida nueva y alcance exclusivamente local.
2. Revisar resultado y orden detected → alerted → contained. Una alerta demuestra
   uso del señuelo, no identidad ni intención maliciosa del usuario.
3. Corroborar replay 410 y ausencia de alerta para el control negativo.
4. Si falla transporte, monitor o cierre, conservar error sanitizado y no afirmar
   contención; detener el receptor y repetir solo bajo una tarea autorizada.
5. Conservar JSON, hash, configuración y limitaciones; no copiar el valor.
6. Confirmar cierre de sockets/threads y registrar resultado en la memoria.

## Aplicación futura a la Feria

En un incidente real, el propietario debe confirmar alcance, revocar/rotar la
credencial real en su proveedor, retirar la exposición y verificar el control,
sin usar la clave hallada para comprobarla. Este piloto no automatiza esas
acciones ni autoriza ejecutarlas. Antes de anunciar utilidad operativa pendiente:
canal de alerta independiente, integración opt-in del caso, diez activaciones
con protocolo congelado, límites del canal y análisis de falsos negativos.

## Incremento IPC — protocolo del piloto antes de medir

El modo `--alert-output` es opt-in: tras registrar la alerta en memoria, el
monitor inicia otro proceso Python mediante stdin, sin red. Solo envía versión,
tipo de evento, condición sintética y timestamp UTC; nunca valor, digest,
cabeceras, ruta, URL ni cliente del señuelo. El receptor valida el esquema exacto,
escribe un JSON nuevo, cierra el archivo y confirma recepción. Esto demuestra
entrega a otro proceso **en el mismo computador**, no correo, webhook, lectura
humana ni almacenamiento resistente a fallos. No se garantiza fsync o persistencia
tras pérdida de energía. El receptor no es un servicio permanente de monitoreo.

Se fija un piloto único `HONEY-IPC-001`, separado del piloto previo y del lote
E4 final: control desconocido 404 sin alerta, activación 204, confirmación de
entrega a receptor separado y replay 410. Se exige concordancia exacta del UTC
del evento enviado con el recibido. Ambas salidas deben ser nuevas, fuera del
repositorio y con directorio padre existente. No sobrescribir evidencia previa.

```powershell
python scripts/run_honeytoken_pilot.py `
  --output ../tmp/HONEY-IPC-001-20260915.json `
  --alert-output ../tmp/HONEY-IPC-001-alert-20260915.json
```

El child tiene timeout de 3 s y acepta hasta 2.048 bytes. Su fallo o rechazo
no impide invalidar el señuelo: el reporte indica entrega fallida y no aprueba
el piloto aunque contención y replay aprueben. La CLI rechaza un archivo de
alerta existente antes de abrir sockets; las regresiones fuerzan el rechazo
del receptor por separado para comprobar esa contención ante fallo.

Los tiempos experimentales IPC se calculan **solo en el proceso principal**:
activación→confirmación de entrega y confirmación→invalidación. La primera
incluye inicio del proceso receptor, validación, escritura y retorno; no es
latencia pura de IPC. No restar relojes monotónicos de procesos distintos ni
confundir `alerted` (evento local) con `delivered` (confirmación recibida).
UTC correlaciona reportes, no sustituye ese reloj de duración. Se conservan
también las métricas locales anteriores con sus nombres, sin mezclarlas.

Regresiones mínimas: entrega real por subprocess y reporte sanitizado; fallo
de entrega sin sobrescritura y con contención; esquema extra/UTC inválido
rechazados antes de escribir. Sus activaciones no integran E4. Integración del
caso y lote final siguen pendientes, incluso si este piloto aprueba.
