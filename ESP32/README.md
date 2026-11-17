# ESP32 · Stand RFID

[`InventarioRFID/InventarioRFID.ino`](InventarioRFID/InventarioRFID.ino) lee tres RC522 y comunica sus eventos a la API Thesora en `https://thesora.redskycol.com/api`. El backend administra el mapeo de UID a posiciones y confirma los préstamos y devoluciones.

## Qué hace

- Mantiene la lectura de hasta cuatro tags por lector, la detección de retiros a los 800 ms y el inventario inicial de tres segundos.
- Descarga el mapeo al conectar y cada diez segundos; conserva la última configuración válida en Preferences. Una posición admite varios activos.
- Consulta las señales LED cada dos segundos y comunica heartbeat cada treinta segundos.
- Mantiene hasta 64 eventos en RAM, en lotes de ocho, mientras no hay conectividad. Reintenta el mismo lote hasta recibir un ACK completo; no considera 409 o una respuesta JSON incompleta como confirmación. Si la API rechaza el lote (400/422), lo reenvía de uno en uno y descarta solo el evento inválido, para que no bloquee la cola.
- La red corre en una tarea separada: TLS, SNTP y solicitudes lentas no bloquean el bucle de lectura.
- La cola RAM no sobrevive al reinicio; si se llena, informa por Serial que se perdió un evento.

No hay UID físicos fijados en el sketch. Los UID se registran desde etiquetas realmente leídas; los datos del servidor por sí solos no prueban una correspondencia con los tags físicos.

## LEDs (uno por lector)

| LED | Significado |
|---|---|
| Fijo | La app pidió señalar ese sitio (`senalizar`) |
| Parpadeo rápido | Hay un objeto que no va en ese sitio, o un tag desconocido |
| Apagado | Normal |

## Piezas

- ESP32 DevKit (ESP32-WROOM)
- 3 × lector RC522 y tags MIFARE de 13,56 MHz
- 3 × LED + 3 × resistencia de 220–330 Ω
- Recomendado: condensador de 10–100 µF entre 3,3 V y GND

## Cableado

| Señal | Pin ESP32 | Va a |
|---|---|---|
| 3,3 V | 3V3 | `3.3V` de los tres lectores |
| GND | GND | `GND` de los lectores y cátodo de los LED |
| SCK | GPIO 18 | `SCK` de los tres lectores |
| MISO | GPIO 19 | `MISO` de los tres lectores |
| MOSI | GPIO 23 | `MOSI` de los tres lectores |
| SS lector 1 | GPIO 5 | `SDA` del lector 1 |
| SS lector 2 | GPIO 4 | `SDA` del lector 2 |
| SS lector 3 | GPIO 25 | `SDA` del lector 3 |
| LED lector 1 | GPIO 22 | resistencia → ánodo del LED |
| LED lector 2 | GPIO 17 | resistencia → ánodo del LED |
| LED lector 3 | GPIO 26 | resistencia → ánodo del LED |

`IRQ` y `RST` del RC522 quedan sin conectar (si un lector no responde, unir su `RST` a 3,3 V).

> **No alimentar el RC522 con 5 V.** Es un componente de 3,3 V.

- Separar los lectores al menos 10 cm para que un tag no se lea en dos a la vez.
- Cables SPI cortos (menos de 20 cm).
- Probar primero un lector solo y añadir los otros de uno en uno. Si al añadir uno fallan los demás, el problema está en el cableado de ese.

Para añadir un cuarto lector, copiar las tres líneas de `LECTOR 3` con otro pin libre (por ejemplo GPIO 27) y añadirlo a `LECTORES[]` y `PIN_LED[]`. En Administración registra el canal del nuevo lector y su posición. La posición puede contener varios activos.

## Dependencias y compilación

Verificado con **Arduino CLI 1.2.0**, placa **ESP32 Dev Module** (`esp32:esp32:esp32`), core **Espressif 3.2.0**, **RFID_MFRC522v2 2.0.6** y **ArduinoJson 7.4.3**. WiFi, HTTPClient, WiFiClientSecure, Preferences y SPI vienen con el core.

El archivo histórico `old-InventarioRFID.ino` se conserva sin cambios. Arduino concatena todos los `.ino` de una carpeta: prepara un directorio de compilación que contenga únicamente el sketch actual, para evitar definiciones duplicadas. Por ejemplo, desde la raíz:

```powershell
New-Item -ItemType Directory -Force .local-dev/arduino/sketch/InventarioRFID
Copy-Item ESP32/InventarioRFID/InventarioRFID.ino .local-dev/arduino/sketch/InventarioRFID/InventarioRFID.ino
arduino-cli compile --fqbn esp32:esp32:esp32 --build-path .local-dev/arduino/build .local-dev/arduino/sketch/InventarioRFID
```

Instala las dos bibliotecas mediante Library Manager o añade `--libraries <directorio>` si las mantienes fuera del sketchbook. Los artefactos temporales de compilación no se versionan.

## Registrar y configurar el stand

1. Un administrador registra el dispositivo `stand-01` en Thesora y conserva su clave, entregada solo al crearlo.
2. Registra sus lectores con canales **1, 2 y 3**, cada uno asociado a su posición física. Asigna los activos y sus UID RFID a esas posiciones.
3. Crea `InventarioRFID/secrets.h`, junto al `.ino`. Está en `.gitignore`, así que no se sube:

   ```cpp
   #pragma once
   #define SECRET_WIFI_SSID      "TU_WIFI"     // red de 2.4 GHz
   #define SECRET_WIFI_PASS      "TU_CLAVE"
   #define SECRET_DEVICE_API_KEY "TU_CLAVE_DEL_DISPOSITIVO"
   ```

   Si falta, el sketch compila con valores de ejemplo y avisa con un `#warning`. `API_URL` y `DISPOSITIVO_ID` (`stand-01`) se editan en el `.ino`.

4. Selecciona **ESP32 Dev Module** y el puerto de la placa. Compila y carga únicamente el sketch actual preparado en el directorio de compilación. Si queda en `Connecting...`, mantén BOOT.
5. Abre Serial Monitor a **115200** baudios. Comprueba WiFi, sincronización de hora, descarga de configuración y lotes confirmados.

No versiones contraseñas WiFi ni claves reales: van solo en `secrets.h`. La clave de dispositivo guardada en el único `.env` raíz como `THESORA_DEVICE_API_KEY` se copia solo a ese archivo. La carpeta `build/` de **Export Compiled Binary** también está ignorada, porque los binarios llevan las claves dentro.

## Leer o escribir un tag

[`EscribirTag/EscribirTag.ino`](EscribirTag/EscribirTag.ino) es una herramienta aparte, sin WiFi, que usa solo el lector 1 (GPIO 5) con el mismo cableado. Muestra el UID de un tag para registrarlo en Thesora (**Administración → Activos → UID RFID**) y puede escribir un texto de hasta 16 caracteres en el tag (por ejemplo `ACT-004`). Si los lectores 2 y 3 siguen conectados, los deja inactivos.

1. Carga `EscribirTag` y abre el Serial Monitor a 115200, con fin de línea **Newline**.
2. Escribe el texto, pulsa Enter y acerca el tag. Responde `ESCRITO Y VERIFICADO`. Un Enter vacío cancela.
3. Para volver al stand, carga otra vez `InventarioRFID`.

El stand identifica los activos por el UID, no por el texto, así que escribir es opcional.

## Contrato del dispositivo

Todas las peticiones incluyen `X-Device-Key`, con una clave propia del ESP32:

| Operación | Petición y respuesta |
|---|---|
| Mapeo | `GET /dispositivos/stand-01/configuracion` → `[{uid,activo_id,codigo,canal}]` |
| LED | `GET /dispositivos/stand-01/senales` → `{canales:[1,2,3]}` con los canales solicitados |
| Eventos | `POST /dispositivos/stand-01/eventos` con `{arranque,eventos:[{secuencia,tipo,canal,uid,antiguedad_ms}]}` → HTTP 202 `{aceptados,duplicados}` |
| Heartbeat | `POST /dispositivos/stand-01/heartbeat` con `{arranque,firmware,rssi}` → HTTP 204 |

`INICIO` envía `canal:null` y `uid:null`; los demás eventos informan el canal y UID. `antiguedad_ms` se calcula nuevamente al retransmitir para conservar la antigüedad de la observación. La deduplicación usa dispositivo, arranque y secuencia.

Un lote solo se retira cuando `aceptados + duplicados` coincide con su cantidad. Ante un error de autenticación (401) o de red se conserva y se reintenta. Ante un error de validación (400/422) se reenvía evento por evento y se descarta solo el que la API rechaza (por ejemplo, de un canal no registrado), con `[API] Evento n descartado` en el Serial Monitor; el resto de canales sigue funcionando. Una configuración inválida o mayor a 64 registros conserva la caché anterior. Un canal mayor que los lectores del sketch no invalida el mapeo: se muestra como aviso.

Un activo cuya posición tiene varios lectores aparece una vez por canal en el mapeo; el stand lo considera correcto en cualquiera de ellos.

`PRESENTE` representa inventario al encender; no confirma por sí solo una devolución. El backend determina si un retiro o devolución corresponde al préstamo y posición esperados.

## TLS y problemas frecuentes

El firmware verifica certificado y nombre del servidor con la CA oficial **GTS Root R4**, usada por la cadena del dominio al verificar esta integración. SNTP (`pool.ntp.org`, `time.nist.gov`) establece la hora antes de las peticiones TLS, sin detener los lectores. Sin hora válida, certificado válido o conectividad se conserva la operación para reintentar; no se desactiva TLS.

| Mensaje o problema | Revisar |
|---|---|
| `LECTOR n: NO RESPONDE` | 3,3 V, GND, SPI 18/19/23 y SS correspondiente |
| Lecturas erráticas | Cableado corto, alimentación y separación entre lectores |
| `[WIFI] Sin WiFi` | SSID, contraseña y red de 2,4 GHz |
| Esperando sincronización de hora | Acceso DNS/NTP de la red |
| Sin respuesta TLS | Fecha, dominio, cadena de certificados y CA configurada |
| `[API] Error HTTP 401` | Clave propia e identificador del dispositivo |
| `[API] Error HTTP 422` + `Evento n descartado` | Ese canal no está registrado para el dispositivo en Thesora, o el formato del evento |
| `LECTOR n: NO RESPONDE (0xFF…)` / `(0x00…)` | 0xFF: MISO, SDA o lector desconectado. 0x00: 3,3 V y GND, o unir `RST` a 3,3 V |
| Configuración inválida | Mapeo y límite local de 64 registros |
| `AVISO: … asignado al cajon n, que no existe` | Hay un lector registrado en Thesora con un canal que este sketch no tiene |
| `TAG DESCONOCIDO` | Registrar el UID real del activo y su posición en Administración |

Si cambia la CA del dominio, actualiza el certificado desde el emisor oficial y recompila. No sustituyas la verificación por `setInsecure()`.

Referencias: [contrato API](../docs/03-api/openapi.yaml), [ejemplo HTTPS de Espressif](https://github.com/espressif/arduino-esp32/blob/3.2.0/libraries/HTTPClient/examples/BasicHttpsClient/BasicHttpsClient.ino), [CA oficial GTS Root R4](https://pki.goog/repo/certs/gtsr4.pem) y [ArduinoJson](https://arduinojson.org/v7/api/jsondocument/).

La compilación y revisión del contrato no sustituyen una prueba con ESP32, lectores, tags y WiFi físicos.
