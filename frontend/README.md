# Thesora · Prototipo navegable

Prototipo en React (Vite) de los flujos descritos en *Thesora: diseño y comportamientos* y el *Manual de marca*.
No hay backend: los datos viven en `src/data.js` y las lecturas QR/RFID se simulan con una espera de 1,8 s.

```bash
npm install
npm run dev
```

- `src/App.jsx`: tabla de rutas (navegación por hash, `src/router.jsx`).
- `src/screens/`: una pantalla por paso de cada flujo.
- `src/components.jsx`: cabecera, navegación, filas de recurso, mapa del estante, avisos.
- `src/index.css`: colores, tipografía y espaciado del manual de marca.
- `#/flujos` (botón «Flujos»): índice con acceso directo a todas las pantallas, incluidas las excepciones.
