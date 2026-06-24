from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_async_database_url(url: str) -> str:
    """
    Ensure the URL uses an async PostgreSQL driver.

    Render/Heroku provide postgres:// or postgresql:// (psycopg2).
    SQLAlchemy async requires postgresql+asyncpg://.
    """
    if "+asyncpg" in url:
        return url
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "Product Catalog API"
    app_env: str = "development"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/product_catalog"

    @property
    def async_database_url(self) -> str:
        return normalize_async_database_url(self.database_url)

    default_page_limit: int = 20
    max_page_limit: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()
