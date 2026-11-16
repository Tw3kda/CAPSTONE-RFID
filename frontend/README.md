# Thesora · Prototipo navegable

Prototipo en React (Vite) de los flujos descritos en *Thesora: diseño y comportamientos* y el *Manual de marca*.
No hay backend: los datos viven en `src/data.js` y las lecturas QR/RFID se simulan con una espera de 1,8 s.

```bash
npm ci
npm run dev
```

El entorno completo y las instrucciones de Docker/Dokploy se encuentran en
[`../README.md`](../README.md). Vite lee el único `.env` de la raíz y dirige
`/api` al backend local; no crear un `.env` dentro de `frontend/`.

- `src/App.jsx`: tabla de rutas (navegación por hash, `src/router.jsx`).
- `src/screens/`: una pantalla por paso de cada flujo.
- `src/components.jsx`: cabecera, navegación, filas de recurso, mapa del estante, avisos.
- `src/index.css`: colores, tipografía y espaciado del manual de marca.
- `#/flujos` (botón «Flujos»): índice con acceso directo a todas las pantallas, incluidas las excepciones.
