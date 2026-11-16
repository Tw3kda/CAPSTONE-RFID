from contextlib import asynccontextmanager
import logging

from fastapi import APIRouter, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine.dispose()


app = FastAPI(
    title="Thesora infrastructure",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
health = APIRouter(prefix="/api/health", tags=["Infraestructura"])


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
