# Prueba de restauración física SOPS

Protocolo definido antes de ejecutar SOPS-RESTORE-001, 16 de septiembre de 2026.
El propietario declaró transcribir su respaldo en papel en el archivo externo
preparado. El agente no observa el papel ni registra contenido de la identidad.
Esta declaración delimita la procedencia; no es un ensayo en un equipo perdido.

## Diseño mínimo y seguridad

- Dos fixtures sintéticos congelados: framework (dos destinatarios age) y réplica
  (un destinatario age). Ninguna clave API o credencial emitida de aplicación.
- Antes de descifrar, verificar archivo externo no vacío, regular y ACL protegida
  de usuario actual. No copiar, imprimir o modificar identidad operativa/restaurada.
- Fuentes Git limpias y SHA completos. No generar otro fixture ni ajustar reglas.
- Por fixture ejecutar, en procesos distintos y sin reintentos: negativo sin
  identidad, positivo con archivo transcrito y negativo posterior sin identidad.
- Entorno del hijo construido por lista blanca: rutas Windows de configuración
  y perfil apuntan a carpeta temporal vacía; no se heredan variables SOPS,
  identidades SSH o credenciales de proveedores. Solo el positivo recibe
  `SOPS_AGE_KEY_FILE`; orden de descifrado age y fixtures sin claves de otros backends.
- El positivo debe aprobar MAC predeterminado SOPS y hash semántico esperado;
  ambos negativos deben completar proceso pero rechazar descifrado. Un timeout
  o proceso inexistente no se considera control negativo aprobado.
- Capturar stdout/stderr en memoria, nunca imprimir o guardar texto claro. Solo
  booleanos, commits, hashes de ciphertext/configuración sintética y UTC.
- Eliminar carpeta vacía de aislamiento; conservar copia transcrita protegida
  hasta recibir autorización específica del propietario para eliminarla.

La selección de un archivo por sí sola no aísla otras identidades: la
[implementación SOPS 3.13.3](https://github.com/getsops/sops/blob/v3.13.3/age/keysource.go)
carga referencias de entorno, configuración por defecto e identidades SSH.
La sustitución de APPDATA/USERPROFILE ocurre solo en el proceso hijo; no cambia
variables persistentes del usuario ni renombra su identidad operativa.

## Ejecución autorizada

Desde framework limpio con SOPS ya instalado y réplica limpia disponible:

```powershell
python scripts/verify_sops_physical_restore.py `
  --key-file <RUTA_CLAVE_AGE>\keys.txt `
  --case-root <RUTA_PROYECTO_CASO> `
  --output ../tmp/SOPS-RESTORE-001-20260916.json
```

La ruta específica corresponde al ensayo de este host. No llevar la identidad
al repo para reproducirlo. El reporte debe ser nuevo; conservar fallos completos
sanitizados y solicitar corrección al propietario si no descifra. No reintentar
con la identidad operativa para convertir un respaldo fallido en éxito.

La prueba es funcional, no benchmark de recuperación, simulación de desastre,
validación de custodia física, redundancia del papel, revocación, CI o Cloud.
No prueba borrado criptográfico de memoria, swap o datos borrados del disco.
