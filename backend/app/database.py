from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_settings

engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 3},
)


def get_db():
    with Session(engine, expire_on_commit=False) as session:
        yield session
