# Requerimientos no funcionales — Thesora

## Rendimiento y continuidad

- **RNF-01.** Con 50 usuarios concurrentes consultando activos y registrando préstamos, al menos el 95 % de las respuestas HTTP debe completarse en menos de 500 ms en el entorno de prueba.
- **RNF-02.** Con 50 clientes conectados, un cambio confirmado en backend debe notificarse por WebSocket en menos de 1 segundo en el entorno de prueba.
- **RNF-03.** El backend debe admitir eventos de 10 lectores, cada uno enviando 1 evento por segundo, sin descartes durante la prueba.
- **RNF-04.** Una desconexión de red no debe detener la lectura RFID ni la señalización local del ESP32.
- **RNF-05.** El ESP32 debe reintentar el envío de eventos no confirmados mientras permanezca encendido; si se llena la cola, debe reportarlo. La cola actual en RAM no garantiza supervivencia a reinicios.
- **RNF-06.** El backend debe responder de forma idempotente a eventos retransmitidos con el mismo dispositivo, arranque y secuencia.

## Seguridad y datos

- **RNF-07.** Las conexiones públicas de la aplicación y de los ESP32 con la API deben usar HTTPS y verificación válida del certificado TLS.
- **RNF-08.** Cada ESP32 debe autenticarse con su propia credencial; el backend debe guardar únicamente su representación protegida, nunca la clave en texto claro.
- **RNF-09.** El backend debe verificar permisos en cada operación protegida, independientemente de las restricciones visuales del frontend.
- **RNF-10.** El acceso por ID exige una clave de 12 a 128 caracteres, sin recortar espacios, protegida mediante Argon2id con sal aleatoria de 16 bytes, memoria de 19 MiB, dos iteraciones y un grado de paralelismo. Las claves son de escritura: alta obligatoria y restablecimiento administrativo opcional; nunca se devuelven claves, hashes ni entradas sensibles en errores de validación. Las cuentas legadas sin clave no acceden por ID hasta su asignación. El QR completo autentica sin clave, verificando cuenta activa, ID numérico registrado y vínculo de carné; su sufijo de seis hexadecimales se ignora tras validar el formato. Una copia de la parte estable de un carné permite suplantar al titular, limitación aceptada; no hay integración Microsoft ni segundo factor. ID y QR se almacenan como HMAC, correo cifrado.
- **RNF-11.** El sistema debe limitar la recolección de datos personales a los necesarios para operar y registrar acciones relevantes de administración.
- **RNF-12.** Los préstamos cerrados deben conservarse ordinariamente 24 meses; los eventos RFID no vinculados, 90 días; la auditoría, 12 meses, salvo obligación legal o instrucción institucional aplicable.

## Despliegue y compatibilidad

- **RNF-13.** Frontend, backend y PostgreSQL deben poder desplegarse mediante contenedores Docker en el VPS administrado con Dokploy; PostgreSQL no debe exponerse públicamente.
- **RNF-14.** La aplicación debe estar disponible en `https://thesora.redskycol.com` y la API bajo `/api` del mismo dominio.
- **RNF-15.** Los flujos de búsqueda, préstamo y devolución deben funcionar en escritorio y móvil, manteniendo fija la navegación inferior móvil durante el desplazamiento del contenido.
- **RNF-16.** El backend debe publicar el contrato OpenAPI utilizado para integrar el frontend y ejecutar pruebas automatizadas de reglas de préstamo, devolución y autorización.
