# Supabase

[`schema.sql`](schema.sql) crea todo lo necesario. Se puede ejecutar varias veces sin perder datos.

## Instalación

1. En <https://supabase.com> crear un proyecto.
2. **SQL Editor → New query**, pegar `schema.sql` completo y pulsar **Run**.
3. En **Project Settings → API** copiar la **Project URL** y la **anon / publishable key** para el ESP32.
   No usar nunca la `service_role` / secret key fuera del panel.

## Tablas

| Tabla | Qué guarda | Quién escribe |
|---|---|---|
| `recursos` | Catálogo, qué tag lleva cada recurso, en qué lector va y dónde está ahora | Admin (panel) y el trigger |
| `eventos` | Historial de todo lo que detectan los lectores | El ESP32 (solo inserta) |
| `dispositivos` | Cada stand ESP32 y su último latido | El ESP32 y el trigger |

### `recursos`

| Columna | Significado |
|---|---|
| `id`, `nombre`, `categoria`, `tipo`, `gabinete`, `estante`, `posicion` | Catálogo, igual que en la app |
| `en_revision` | Equipo en mantenimiento |
| **`uid_tag`** | UID del tag pegado al recurso. Se acepta `AF91D01C`, `AF:91:D0:1C` o `0xAF, 0x91, …` |
| **`dispositivo_id`** | Stand donde va (`stand-01`) |
| **`lector`** | Lector de ese stand donde va. Vacío = cualquiera |
| `presente`, `dispositivo_actual`, `lector_actual`, `actualizado_en` | Estado en vivo. Los escribe el trigger: no editar a mano |
| `senalizar_hasta` | Hasta cuándo está encendido el LED de su lector |

### `eventos`

| Columna | Significado |
|---|---|
| `evento` | `INICIO` (el stand encendió), `PRESENTE` (estaba al encender), `DEVUELTO` (apareció), `RETIRADO` (desapareció) |
| `uid`, `lector`, `dispositivo_id` | Lo que vio el ESP32 |
| `recurso_id` | Recurso al que corresponde el UID (vacío si es desconocido) |
| `resultado` | `OK`, `LUGAR_INCORRECTO` o `DESCONOCIDO` |
| `ocurrido_en` | Hora real del evento (aunque haya llegado tarde por falta de WiFi) |

## Cambiar qué tag va en qué lector

**Table Editor → `recursos`** y editar `uid_tag`, `dispositivo_id` y `lector`. El ESP32 descarga el cambio en menos de 30 s, sin volver a cargar el sketch.

Para registrar un tag nuevo: ponerlo sobre un lector; el Serial Monitor muestra `TAG DESCONOCIDO: XXXXXXXX` y la tabla `eventos` tiene una fila con `resultado = DESCONOCIDO` y ese `uid`. Copiar el UID en `uid_tag`.

## Para quien hace la app

Todo se lee con la anon key. La app puede:

| Necesidad de la app | Cómo |
|---|---|
| Disponible / Prestado | `recursos.presente` (y `en_revision`) |
| Esperar la lectura RFID en vivo | Realtime sobre `eventos` (INSERT), filtrando por `recurso_id` |
| Recurso inesperado / incorrecto | Evento con `resultado` ≠ `OK`, o `recurso_id` distinto del esperado |
| Ubicación no confirmada | `recursos.lector_actual` ≠ `recursos.lector` |
| Indicador luminoso | `rpc('senalizar', { p_recurso: 'ACT-004', p_segundos: 30 })`; con `0` se apaga. También se apaga solo al colocar el recurso en su lector |
| Stand desconectado | Vista `dispositivos_estado` (`en_linea`) |
| Historial y análisis | `eventos` ordenado por `ocurrido_en` |

El ESP32 no sabe **quién** retira: eso lo pone la app. La tabla de préstamos y usuarios todavía no existe; queda para el backend.

La anon key **no** puede modificar `recursos` ni borrar nada. Para que la app edite el catálogo hará falta añadir reglas para usuarios autenticados.

## Pruebas

`tests/` ejecuta `schema.sql` en un Postgres local y simula al ESP32 (arranque, retiros, devoluciones en lugar incorrecto, tags desconocidos, reintentos duplicados, cambio de mapeo, LEDs, permisos). No toca el proyecto real.

```bash
cd Supabase/tests && npm install && npm test
```
