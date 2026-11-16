from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings
from sqlalchemy import URL


class Settings(BaseSettings):
    # Compose injects only these settings from the repository's root .env.
    postgres_db: str
    postgres_user: str
    postgres_password: SecretStr
    postgres_host: str = "db"
    postgres_port: int = 5432
    auth_signing_key: SecretStr | None = None
    data_encryption_key: SecretStr | None = None
    access_token_seconds: int = 900
    refresh_token_seconds: int = 604800
    secure_cookies: bool = True

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
