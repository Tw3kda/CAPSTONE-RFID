# Requerimientos funcionales — Thesora

## Acceso y usuarios

- **RF-01.** El sistema debe autenticar mediante ID institucional y clave, o mediante QR del carné sin clave. Cada alta requiere ID y clave de 12 a 128 caracteres; el QR es opcional y se registra explícitamente por un administrador. El QR completo tiene formato E000000000 + ID numérico de longitud variable + seis caracteres hexadecimales finales; se valida contra el ID registrado y su vínculo de carné. El sufijo cambia y no forma parte de la identidad; se conserva solo el HMAC canónico del prefijo e ID. No se da acceso por QR a cuentas sin carné asociado. Los roles siempre provienen del servidor.
- **RF-02.** El backend debe aplicar los roles Usuario, Encargado y Administrador a las operaciones protegidas.
- **RF-03.** El administrador debe poder gestionar usuarios y sus roles.

## Inventario y ubicación

- **RF-04.** La aplicación debe permitir buscar activos por nombre, código o categoría y filtrar por disponibilidad. Una ausencia física confirmada impide ofrecer o preparar otro préstamo, aunque no exista préstamo registrado; no se inventa responsable, préstamo ni estado de mantenimiento.
- **RF-05.** La ficha de un activo debe mostrar nombre, categoría, código, disponibilidad, condición y ubicación asignada.
- **RF-06.** La aplicación debe indicar el espacio, gabinete, estante y posición del activo consultado.
- **RF-07.** El administrador debe poder gestionar activos, categorías y posiciones asignadas.

## Préstamos y devoluciones

- **RF-08.** El usuario debe poder preparar un préstamo a su nombre; el encargado, también a nombre de otro usuario.
- **RF-09.** Todo préstamo debe registrar activo, responsable, persona que entrega y devolución esperada.
- **RF-10.** El backend debe confirmar el retiro únicamente cuando reciba la detección física del RFID correspondiente al préstamo pendiente.
- **RF-11.** La aplicación debe mostrar los préstamos activos, su fecha de devolución y el historial accesible según el rol.
- **RF-12.** Al iniciar una devolución, el sistema debe verificar que el RFID leído corresponde al activo prestado.
- **RF-13.** Si el RFID no coincide, la aplicación debe informar el error y permitir repetir la lectura sin cerrar el préstamo.
- **RF-14.** El backend debe cerrar el préstamo únicamente cuando el activo sea detectado en su posición asignada.
- **RF-15.** Si el activo aparece en otra posición, la aplicación debe indicar la ubicación correcta y el préstamo debe permanecer abierto.
- **RF-16.** El usuario debe poder cancelar una operación de retiro o devolución aún no completada, sin registrar una confirmación física inexistente.

## Lectores RFID

- **RF-17.** El ESP32 debe detectar varios tags en un mismo lector y distinguir presencia, ausencia y retiros.
- **RF-18.** El ESP32 debe activar el LED del lector indicado por el backend y señalar localmente una posición con un objeto incorrecto.
- **RF-19.** El administrador debe poder asociar un lector físico a una posición y varios activos a una misma posición.
- **RF-20.** El ESP32 debe obtener del backend el mapeo de RFID a posiciones y conservar la última configuración válida para operar sin conexión.
- **RF-21.** El ESP32 debe encolar eventos durante una desconexión y reintentar su transmisión al recuperar conectividad.
- **RF-22.** El ESP32 debe comunicar periódicamente su estado de conexión al backend.
- **RF-23.** El backend debe registrar los eventos RFID, admitir UID desconocidos e impedir el procesamiento duplicado de reintentos.
- **RF-24.** La aplicación debe reflejar los cambios confirmados por el backend sin requerir recarga manual. El retiro sin préstamo emite un aviso de inventario; la reposición recupera la disponibilidad física sin cerrar préstamos que no hayan iniciado devolución. La presencia se conserva separada del estado de negocio y los eventos antiguos no revierten observaciones más recientes.

## Análisis

Todo el módulo de análisis, incluidos indicadores, recursos reutilizables y recomendación IA, es exclusivo del Administrador. Usuario y Encargado reciben 403 en sus tres endpoints; el acceso ordinario al inventario y a préstamos conserva sus permisos.

- **RF-25.** La aplicación debe mostrar disponibilidad, uso por período y recursos con baja utilización.
- **RF-26.** La aplicación debe permitir generar mediante OpenAI una recomendación sobre reutilización o mantenimiento basada en métricas agregadas y candidatos del inventario. Debe permitir ocultarla y volver a mostrarla sin otra llamada; regenerar requiere una acción explícita. Los fallos del proveedor deben mostrarse como errores, sin simular una respuesta de IA mediante reglas locales.
- **RF-27.** Desde la recomendación, el administrador debe poder consultar las fichas de los recursos sugeridos.

El análisis usa una ventana móvil de 90 días en UTC. La baja utilización se refiere a activos
disponibles sin retiros físicos confirmados en ese período; no se cuentan preparaciones ni
operaciones canceladas sin retiro. El uso semanal agrupa retiros confirmados por lunes e incluye
semanas sin movimientos. Las recomendaciones son descriptivas y marcan datos insuficientes
si no existe evidencia de seguimiento de 90 días para todos los activos sugeridos. Ocultar y
volver a mostrar la recomendación es una interacción de presentación, sin borrar historial.
