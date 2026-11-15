# ESP32 · Stand RFID

[`InventarioRFID/InventarioRFID.ino`](InventarioRFID/InventarioRFID.ino) lee los RC522 y envía a Supabase cada tag que aparece o desaparece.

## Qué hace

- **Envía eventos** con el UID y el número de lector: `DEVUELTO` cuando un tag aparece y `RETIRADO` cuando lleva 0,8 s sin leerse.
- **Inventario al encender**: durante los primeros 3 s envía `PRESENTE` por cada tag que encuentra, y Supabase corrige lo que cambió mientras estuvo apagado.
- **Mapeo desde Supabase**: descarga qué tag va en qué lector al conectar y cada 30 s, y lo guarda en la flash para funcionar sin WiFi.
- **Sin WiFi** guarda hasta 64 eventos y los envía al volver, con su hora real. Los reintentos no duplican filas.
- **Latido** cada 30 s para que la app sepa si el stand está en línea.
- **Varios tags por lector** (hasta 4).
- La red corre en una tarea aparte: una conexión lenta no frena la lectura.

## LEDs (uno por lector)

| LED | Significado |
|---|---|
| Fijo | La app pidió señalar ese sitio (`senalizar`) |
| Parpadeo rápido | Hay un objeto que no va en ese sitio, o un tag desconocido |
| Apagado | Normal |

## Piezas

- ESP32 DevKit (ESP32-WROOM)
- 2 × lector RC522 y tags MIFARE de 13,56 MHz
- 2 × LED + 2 × resistencia de 220–330 Ω
- Recomendado: condensador de 10–100 µF entre 3,3 V y GND

## Cableado

| Señal | Pin ESP32 | Va a |
|---|---|---|
| 3,3 V | 3V3 | `3.3V` de los dos lectores |
| GND | GND | `GND` de los lectores y cátodo de los LED |
| SCK | GPIO 18 | `SCK` de los dos lectores |
| MISO | GPIO 19 | `MISO` de los dos lectores |
| MOSI | GPIO 23 | `MOSI` de los dos lectores |
| SS lector 1 | GPIO 5 | `SDA` del lector 1 |
| SS lector 2 | GPIO 4 | `SDA` del lector 2 |
| LED lector 1 | GPIO 22 | resistencia → ánodo del LED |
| LED lector 2 | GPIO 17 | resistencia → ánodo del LED |

`IRQ` y `RST` del RC522 quedan sin conectar (si un lector no responde, unir su `RST` a 3,3 V).

> **No alimentar el RC522 con 5 V.** Es un componente de 3,3 V.

- Separar los lectores al menos 10 cm para que un tag no se lea en los dos.
- Cables SPI cortos (menos de 20 cm).
- Probar primero un lector solo y luego añadir el segundo.

Para añadir un lector, copiar las tres líneas de `LECTOR 2` con otro pin y añadirlo a `LECTORES[]` y `PIN_LED[]`.

## Arduino IDE

| Componente | Nombre en el IDE |
|---|---|
| Placa | **esp32** de Espressif Systems (probado con 3.3.12) |
| Librería | **RFID_MFRC522v2** (probado con 2.0.6) |

`WiFi`, `HTTPClient`, `WiFiClientSecure` y `Preferences` vienen con la placa ESP32.

## Configurar y cargar

1. Ejecutar antes [`../Supabase/schema.sql`](../Supabase/schema.sql).
2. Abrir `InventarioRFID/InventarioRFID.ino` y editar el bloque inicial:

   ```cpp
   const char* WIFI_SSID = "TU_WIFI";          // solo 2.4 GHz
   const char* WIFI_PASS = "TU_CLAVE";
   const char* SUPABASE_URL = "https://TU-PROYECTO.supabase.co";
   const char* SUPABASE_KEY = "TU_ANON_KEY";
   const char* DISPOSITIVO_ID = "stand-01";
   ```

3. **Tools → Board → esp32 → ESP32 Dev Module** y elegir el puerto COM.
4. **Upload**. Si se queda en `Connecting....`, mantener pulsado **BOOT**.
5. **Serial Monitor** a **115200** baudios.

No subir a GitHub el sketch con la clave del WiFi.

## Problemas frecuentes

| Problema | Revisar |
|---|---|
| `LECTOR n: NO RESPONDE` | 3,3 V, GND, SCK/MISO/MOSI en 18/19/23 y el `SDA` en su pin |
| Un lector funciona solo pero no con el otro | Su `SDA` está en el pin equivocado |
| Lecturas erráticas o reinicios | Cables más cortos, el condensador, un buen puerto USB |
| `[WIFI] Sin WiFi` | SSID, clave y que la red sea de 2,4 GHz |
| `[SUPABASE] Error 401` | Clave incorrecta o incompleta |
| `[SUPABASE] Error 404` | No se ejecutó `schema.sql` |
| `[CONFIG] 0 recursos` | Ningún recurso tiene `dispositivo_id` igual a `DISPOSITIVO_ID` |
| `TAG DESCONOCIDO` | Ese UID no está en `recursos.uid_tag` |

## Seguridad

- La anon key va dentro del firmware. Con las reglas de `schema.sql` solo puede leer, insertar eventos y llamar a `latido` y `senalizar`.
- El sketch no verifica el certificado TLS de Supabase (`setInsecure()`), lo cual vale para un prototipo pero no para producción.
