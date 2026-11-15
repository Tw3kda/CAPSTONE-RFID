# Requerimientos funcionales — Thesora

## Acceso y usuarios

- **RF-01.** El sistema debe permitir identificar a un usuario mediante QR de credencial o identificador institucional, previa validación de la credencial.
- **RF-02.** El backend debe aplicar los roles Usuario, Encargado y Administrador a las operaciones protegidas.
- **RF-03.** El administrador debe poder gestionar usuarios y sus roles.

## Inventario y ubicación

- **RF-04.** La aplicación debe permitir buscar activos por nombre, código o categoría y filtrar por disponibilidad.
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
- **RF-24.** La aplicación debe reflejar los cambios confirmados por el backend sin requerir recarga manual.

## Análisis

- **RF-25.** La aplicación debe mostrar disponibilidad, uso por período y recursos con baja utilización.
- **RF-26.** La aplicación debe permitir generar, ocultar y volver a mostrar una recomendación sobre reutilización o mantenimiento basada en los datos existentes.
- **RF-27.** Desde la recomendación, el usuario debe poder consultar las fichas de los recursos sugeridos.
