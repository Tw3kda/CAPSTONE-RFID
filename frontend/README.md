# Thesora · Frontend

Aplicación React/Vite integrada con la API FastAPI y el canal WebSocket del mismo origen. El backend confirma la identidad, los permisos y cada cambio físico de préstamo o devolución.

## Desarrollo y verificación

Desde `frontend/`:

```powershell
npm ci
npm run dev
npm test
npm run lint
npm run build
```

Vite escucha en http://127.0.0.1:5173 y dirige HTTP y WebSocket de `/api` a http://127.0.0.1:8001. Lee el único `.env` de la raíz mediante `envDir`; no crear otro en `frontend/`. `VITE_API_BASE_URL=/api` es configuración pública. Las claves de la API, base de datos, dispositivos y proveedor de IA pertenecen al servidor y nunca deben usar el prefijo `VITE_`.

El despliegue de producción usa el build de Vite servido por nginx, con proxy `/api` y upgrade de WebSocket. Véase [la guía principal](../README.md) para Docker Compose y Dokploy.

## Acceso y sesión

El administrador registra un ID universitario y una clave de 12 a 128 caracteres, y puede registrar también el contenido QR del carné. El acceso manual requiere ID y clave; el QR no solicita clave. La normalización del QR pertenece al backend: el frontend envía su contenido completo. La cuenta debe estar activa. No hay cuentas predeterminadas ni verificación Microsoft.

El acceso ofrece ID y clave, lectura de QR con cámara y entrada manual de su contenido. Escanear QR solicita la cámara directamente desde el clic, antes de comprobar el decodificador; no requiere otro botón de activación. El stream vive solo en memoria y se libera al salir o terminar una lectura, incluso si el permiso llega después de cancelar su apertura. Se mantiene la preferencia flexible por cámara trasera, sin exigir un dispositivo concreto, y vídeo silencioso con `playsInline`. La entrada manual queda en un desplegable cerrado. Los errores reciben foco y se desplazan a la vista; una lectura rechazada detiene el escaneo hasta un nuevo intento. La aplicación no simula lecturas.

`BarcodeDetector` es opcional. Si no existe, no admite QR o falla, se carga dinámicamente `jsqr@1.4.0` y se decodifican los fotogramas localmente; no se envían imágenes al servidor. El trabajo se limita a cuatro lecturas por segundo y a 640 píxeles en el lado mayor, conservando proporción. La ruta nativa sigue disponible sin descargar el decodificador alternativo. jsQR es una biblioteca independiente solo para QR, sin dependencias de ejecución; su última versión publicada es de 2021, por lo que no se presupone mantenimiento activo. Se distribuye bajo Apache-2.0 y se incluye [su licencia](public/licenses/jsqr-LICENSE.txt). El tamaño comprimido del fragmento se muestra en `npm run build`.

La cámara requiere HTTPS o localhost. El navegador y el sistema controlan el permiso; una denegación previa, una política de iframe o un navegador integrado pueden impedir que aparezca un aviso. No se intenta eludir esas restricciones. Se distingue permiso denegado, cámara ausente o inaccesible y contexto inseguro; se ofrece reintento explícito, acceso por ID y abrir el enlace directamente en Chrome o Safari cuando corresponda. El soporte de captura no depende del soporte de decodificación nativa. Véanse [getUserMedia y sus errores](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia), [compatibilidad de BarcodeDetector](https://developer.mozilla.org/en-US/docs/Web/API/BarcodeDetector), [política de cámara](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Permissions-Policy/camera), [vídeo en Safari](https://webkit.org/blog/6784/new-video-policies-for-ios/) y [la documentación de jsQR](https://github.com/cozmo/jsQR).

Los tokens se conservan en `sessionStorage` de la pestaña; la clave no se guarda en la sesión ni en el almacenamiento del navegador. El cliente centralizado renueva el acceso ante 401 y coordina renovaciones concurrentes. El handshake WebSocket usa la cookie HttpOnly emitida por el backend, sin tokens en la URL. Salir elimina la sesión de la aplicación y cierra el canal. El backend mantiene su política de caducidad de tokens.

## Pantallas y operaciones

- Acceso y lectura QR; Inicio con búsqueda, acciones rápidas y actividad real.
- Inventario con búsqueda por nombre/código, categoría y disponibilidad; ficha con condición y movimientos; mapa de posiciones reales y solicitud de señal LED.
- Preparación de préstamo propio o delegado para Encargado/Administrador. La búsqueda del destinatario usa nombre o un identificador registrado; el ID interno solo se usa en el payload.
- Mis recursos, historial, detalle y consulta de todos los préstamos para los roles autorizados.
- Retiro pendiente, comprobante, devolución mediante lectura RFID y detección de la posición, comprobante y recuperación ante RFID/posición incorrectos. Cancelar llama al backend. Ningún botón ni temporizador confirma una detección física.
- Análisis exclusivo de Administradores: disponibilidad, retiros semanales, baja utilización y recursos relacionados de los últimos 90 días. Las rutas y enlaces se restringen antes de montar las vistas; Usuario y Encargado no consultan sus endpoints. Generar recomendación y Generar nueva recomendación solicitan un resultado al backend; el botón separado Mostrar/Ocultar conserva el resultado sin otra solicitud. Si falla una nueva generación, se mantiene el resultado anterior y se ofrece reintentar.
- Administración: usuarios y activos con alta/edición; categorías, espacios, gabinetes y posiciones con las altas admitidas por contrato; dispositivos con alta y estado reportado; lectores con alta y reasignación de posición.

La credencial de un dispositivo se muestra únicamente en el resultado de su alta y se elimina de la vista al cerrarlo. Los identificadores y claves de usuarios no se recuperan: los campos vacíos de edición conservan el valor, una nueva clave restablece el acceso y retirar QR requiere marcar una acción explícita. Las claves se envían sin recortar sus espacios.

Las rutas usan hash para admitir alojamiento estático. Los enlaces a operaciones conservan el ID del préstamo; al recargar se consulta de nuevo su estado. Las vistas presentan carga, vacío, errores y recuperación. Las notificaciones WebSocket invalidan consultas y, al reconectar, recuperan datos del servidor. Durante la desconexión se muestra un aviso y se puede actualizar manualmente.

El acceso a Administración se integra en la navegación superior, con menú desplegable en móvil y salida de sesión. No se muestra una barra adicional con el nombre y rol de la cuenta.

## Diseño y accesibilidad

Se conserva el marco, las pantallas y la jerarquía de los [wireframes aprobados](../docs/04-frontend/Thesora_Wireframes_Diseno_y_Comportamientos.pdf), junto con la paleta, tipografía Inter y espaciado del [manual de marca](../docs/04-frontend/Thesora_Manual_de_Marca.pdf). Se reutilizaron las disposiciones y componentes visuales útiles del prototipo; se retiraron datos de demostración, transiciones automáticas e índice de pantallas.

La cabecera importa el SVG oficial `Thesora_Imagotipo_Negativo_Transparente.svg`; el favicon es el isotipo principal oficial, copiados sin alterar geometría. La navegación móvil permanece fija y reserva el área segura inferior. Los formularios tienen etiquetas visibles, los errores se anuncian y las tablas administrativas son semánticas y desplazables en pantallas estrechas.

Las decisiones de administración se apoyan en estas fuentes, sin adoptar otra identidad visual:

- [Carbon: tablas de datos](https://carbondesignsystem.com/components/data-table/usage/): encabezados, búsqueda, acciones por fila y estructura orientada a localizar registros.
- [W3C WAI: etiquetas](https://www.w3.org/WAI/tutorials/forms/labels/) y [notificaciones de formularios](https://www.w3.org/WAI/tutorials/forms/notifications/): controles etiquetados y feedback claro para corregir errores.
- [Nielsen Norman Group: prototipos IA en contextos reales](https://www.nngroup.com/articles/ai-prototyping/) y [especificación de interfaces](https://www.nngroup.com/articles/vague-prototyping/): usar contexto y especificaciones concretas para evitar resultados genéricos. Aquí se aplican el manual y los flujos existentes, con administración utilitaria, sin métricas, degradados o decoración inventados.
- [MDN: Barcode Detection API](https://developer.mozilla.org/en-US/docs/Web/API/Barcode_Detection_API): detección de disponibilidad y alternativas explícitas por compatibilidad.

## Estructura y pruebas

`src/api.js` concentra HTTP, sesión y errores; `src/realtime.js` gestiona el canal y reconexión; `src/session.jsx` coordina la sesión y `src/hooks.js` las consultas. `src/screens/` contiene las vistas y `src/components.jsx` el marco y presentación compartidos.

Vitest y Testing Library verifican comportamiento en los límites HTTP y React: renovación de sesión, permisos y conflictos, preparación de préstamos, confirmación únicamente por estado consultado, errores RFID, edición sin exponer UID y tratamiento de claves de dispositivos. Los dobles de red existen solo en pruebas, nunca como fuente de datos de ejecución.
