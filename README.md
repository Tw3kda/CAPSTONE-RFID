# Thesora · Entorno de desarrollo y despliegue

Aplicación de inventario RFID del capstone. Stack objetivo: FastAPI/Python 3.12, React/Vite y PostgreSQL 16. Los requisitos y el contrato del producto están en `docs/`.

## Desarrollo local

Requisitos: Docker con Compose v2 y Node.js compatible con el Vite del lockfile (Node 22.14 o superior de la rama 22 funciona en este entorno).

Desde la raíz del repositorio:

```powershell
Copy-Item .env.example .env # Solo la primera vez; conservar el .env existente.
# Cambiar POSTGRES_PASSWORD por una contraseña aleatoria antes de iniciar.
docker compose -f docker-compose.dev.yml config --quiet
docker compose -f docker-compose.dev.yml up -d --build --wait
cd frontend
npm ci
npm run dev
```

Existe un único `.env`, en la raíz. Compose lo usa para interpolar variables e inyecta al backend únicamente las de PostgreSQL; Vite lee desde esa misma raíz y publica únicamente variables `VITE_*`. No crear `.env` adicionales por servicio ni entorno. `.env.example` contiene valores de ejemplo y `.env` está ignorado por Git. El `.env` creado durante la configuración local ya contiene una contraseña aleatoria.

- Frontend Vite: http://127.0.0.1:5173
- API directa: http://127.0.0.1:8001/api/health/ready
- API mediante proxy Vite: http://127.0.0.1:5173/api/health/ready
- OpenAPI de las rutas implementadas: http://127.0.0.1:8001/api/docs
- PostgreSQL 16: accesible solo dentro de la red Docker `data`, sin puerto publicado.

`DEV_API_PORT` cambia el puerto host del backend; actualizar también `DEV_API_PROXY_TARGET`. `VITE_DEV_PORT` cambia el puerto de Vite. Los puertos 8001 y 5173 se enlazan solo a loopback. El frontend corre fuera de Docker y el backend recarga al editar `backend/app/`.

El servicio `migrate` ejecuta `alembic upgrade head` una vez antes del backend. El esqueleto Alembic aún no contiene revisiones ni modelos de negocio: solo prepara el mecanismo de migraciones, sin importar el esquema histórico de Supabase. Las futuras migraciones deben revisarse y ejecutarse desde este único servicio.

```powershell
docker compose -f docker-compose.dev.yml ps -a
docker compose -f docker-compose.dev.yml logs --tail 50 backend migrate
Invoke-RestMethod http://127.0.0.1:5173/api/health/ready
docker compose -f docker-compose.dev.yml run --rm migrate alembic current
cd frontend
npm run build
npm run lint
```

Detener Vite con Ctrl+C. Desde la raíz, `docker compose -f docker-compose.dev.yml down` detiene el stack conservando la base de datos. No usar `down -v` para datos que deban conservarse. El volumen de desarrollo es `thesora-dev_db_data` y está separado del proyecto de producción.

## Producción en Dokploy

`docker-compose.yml` construye FastAPI y un frontend estático con Node en la etapa de build y Nginx sin privilegios en ejecución. El proxy Nginx conserva `/api` y permite upgrades WebSocket. No se añade Redis ni workers porque el backend actual no los necesita.

1. En Dokploy crear una aplicación Docker Compose desde este repositorio y seleccionar `docker-compose.yml`.
2. Configurar el único `.env` de la raíz mediante la sección Environment de Dokploy, usando `.env.example` como plantilla y credenciales propias del VPS. No subir el `.env` local al repositorio. Mantener `VITE_API_BASE_URL=/api`; estas variables son públicas y se aplican en build.
3. Verificar que Dokploy dispone de su red externa `dokploy-network`. Solo `frontend` se conecta a ella.
4. En Domains configurar `thesora.redskycol.com`, servicio `frontend`, puerto de contenedor `8080`, ruta `/`, HTTPS y certificado de Let's Encrypt. DNS debe apuntar al VPS. No configurar un segundo dominio para el backend: Nginx dirige `/api` internamente.
5. Desplegar desde Dokploy. El orden es PostgreSQL saludable → migración finalizada → backend saludable → frontend. Revisar healthchecks y logs.

Compose no publica puertos de host en producción. PostgreSQL solo pertenece a la red interna `data`; el backend se comunica con frontend por la red privada `app`. El volumen `db_data` queda asociado al nombre de proyecto de Dokploy. Mantener estable ese nombre y configurar copias de seguridad del volumen antes de alojar datos reales. No almacenar secretos en variables `VITE_*` ni argumentos de build.

La comprobación local del Compose de producción usa un proyecto separado, sin publicar puertos ni contactar el VPS:

```powershell
docker compose -p thesora-prod-check -f docker-compose.yml config --quiet
docker compose -p thesora-prod-check -f docker-compose.yml up -d --build --wait
docker compose -p thesora-prod-check -f docker-compose.yml exec -T frontend wget -qO- http://127.0.0.1:8080/api/health/ready
docker compose -p thesora-prod-check -f docker-compose.yml down
```

Para esta comprobación se necesita que exista `dokploy-network` localmente; si no existe, puede crearse con `docker network create dokploy-network`. Esto no configura DNS, TLS ni un despliegue remoto.

## Alcance actual

El frontend conserva el prototipo y sus datos simulados. El backend nuevo solo implementa `/api/health/live` y `/api/health/ready`; este último ejecuta `SELECT 1` real y devuelve 503 si PostgreSQL falla. La configuración deja listo el transporte `/api`, pero no implementa autenticación, inventario, préstamos ni WebSockets de negocio. `docs/03-api/openapi.yaml` describe el contrato completo objetivo; `/api/openapi.json` refleja solo las rutas que existen hoy.

- `backend/`: arranque FastAPI, configuración SQLAlchemy y Alembic.
- `frontend/`: React/Vite y build de producción.
- `ESP32/`: firmware y cableado.
- `Supabase/`: implementación histórica, no utilizada por este Compose.
- `tmp/`: referencias locales, no utilizadas por el entorno Thesora.
