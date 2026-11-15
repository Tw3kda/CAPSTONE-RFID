# Capstone · Inventario RFID

Stand de laboratorio con lectores RFID: detecta cuando se retira o se devuelve un recurso y lo registra en Supabase.

| Carpeta | Qué contiene |
|---|---|
| [`ESP32/`](ESP32/) | Firmware del stand (Arduino) y guía de cableado |
| [`Supabase/`](Supabase/) | Base de datos: tablas, reglas de seguridad, lógica y pruebas |
| [`FrontEnd/`](FrontEnd/) | App web (React + Vite) |
| [`Backend/`](Backend/) | Vacía por ahora |

## Cómo se conectan

```
 Tags RFID ──► ESP32 ──── eventos (UID + lector) ────►  Supabase  ◄──── lee / escucha ──── FrontEnd
                 ▲                                        │
                 └──── mapeo tag→lector, LEDs a encender ─┘
```

- El **ESP32** solo reporta hechos: qué UID apareció o desapareció en qué lector.
- **Supabase** sabe qué recurso es cada UID y dónde debe ir, y decide si está en su sitio.
- El **FrontEnd** lee el estado y el historial desde Supabase. Detalles en [`Supabase/README.md`](Supabase/README.md).

## Puesta en marcha

1. Crear el proyecto en Supabase y ejecutar [`Supabase/schema.sql`](Supabase/schema.sql).
2. Cablear y cargar el ESP32 siguiendo [`ESP32/README.md`](ESP32/README.md).
3. Asignar los tags a los recursos en Supabase (Table Editor → `recursos`).
