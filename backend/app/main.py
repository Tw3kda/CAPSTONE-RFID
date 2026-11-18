import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.analysis import analysis
from app.database import engine
from app.devices import devices, provisioning, signals
from app.loans import loans
from app.realtime import realtime
from app.routes import administration, auth, inventory

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine.dispose()


app = FastAPI(
    title="Thesora API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
health = APIRouter(prefix="/api/health", tags=["Infraestructura"])


@app.exception_handler(RequestValidationError)
async def invalid_request(request, error: RequestValidationError):
    # Validation must never echo passwords, card content or the submitted body.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {key: issue[key] for key in ("type", "loc", "msg")} for issue in error.errors()
            ]
        },
    )


@health.get("/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@health.get("/ready")
def readiness() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # Do not include connection strings or credentials in HTTP responses/logs.
        logger.warning("Database readiness check failed")
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ok", "database": "ok"}


app.include_router(health)
app.include_router(auth)
app.include_router(inventory)
app.include_router(administration)
app.include_router(loans)
app.include_router(provisioning)
app.include_router(devices)
app.include_router(signals)
app.include_router(realtime)
app.include_router(analysis)


def published_openapi():
    if app.openapi_schema is None:
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        schema.setdefault("components", {}).setdefault("securitySchemes", {})["cookieAuth"] = {
            "type": "apiKey",
            "in": "cookie",
            "name": "thesora_session",
        }
        schema["paths"]["/api/ws/estado"] = {
            "get": {
                "tags": ["Préstamos"],
                "summary": "Cambios confirmados en vivo (WebSocket)",
                "description": "Sesión por cookie HttpOnly o Authorization. "
                "No admite tokens en URL. "
                "JSON: {tipo, activo_id, prestamo_id, estado, detalle}. "
                "Préstamos visibles solo para su responsable y roles autorizados.",
                "security": [{"bearerAuth": []}, {"cookieAuth": []}],
                "responses": {
                    "101": {"description": "Switching Protocols"},
                    "401": {"description": "Sesión inválida"},
                },
                "x-websocket": True,
            }
        }
        app.openapi_schema = schema
    return app.openapi_schema


app.openapi = published_openapi
