import logging
from functools import lru_cache
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# psycopg2/libpq query params — must not be forwarded to asyncpg.connect()
_PSYCOPG2_ONLY_QUERY_PARAMS = frozenset(
    {
        "sslmode",
        "channel_binding",
        "sslcert",
        "sslkey",
        "sslrootcert",
        "sslcrl",
        "sslcompression",
        "requirepeer",
        "gssencmode",
        "krbsrvname",
        "service",
        "target_session_attrs",
        "connect_timeout",  # asyncpg uses command_timeout, not this name
    }
)

# sslmode values that require an encrypted connection (Neon, Render managed Postgres)
_SSL_REQUIRED_MODES = frozenset({"require", "verify-ca", "verify-full"})


def mask_database_url(url: str) -> str:
    """Return URL with password redacted for safe logging."""
    parsed = urlparse(url)
    if not parsed.hostname:
        return url

    port = f":{parsed.port}" if parsed.port else ""
    auth = f"{parsed.username}:***@" if parsed.username else ""
    netloc = f"{auth}{parsed.hostname}{port}"
    return urlunparse(
        (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
    )


def normalize_async_database_url(url: str) -> str:
    """
    Convert any PostgreSQL URL to postgresql+asyncpg:// and strip psycopg2-only
    query parameters (sslmode, channel_binding, etc.) that asyncpg rejects.

    Neon/Render URLs often look like:
      postgresql://user:pass@host/db?sslmode=require&channel_binding=require

    asyncpg does not accept sslmode or channel_binding as connect() kwargs.
    SSL is configured separately via connect_args (see database_connect_args).
    """
    parsed = urlparse(url)

    scheme = parsed.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    elif scheme == "postgresql+asyncpg":
        pass
    else:
        return url

    query = parse_qs(parsed.query, keep_blank_values=False)

    query.pop("sslmode", None)
    query.pop("channel_binding", None)

    for param in list(query):
        if param in _PSYCOPG2_ONLY_QUERY_PARAMS:
            query.pop(param, None)

    flat_pairs: list[tuple[str, str]] = []
    for key, values in query.items():
        for value in values:
            flat_pairs.append((key, value))

    normalized = urlunparse(
        (
            scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(flat_pairs),
            parsed.fragment,
        )
    )
    return normalized


def database_connect_args(url: str) -> dict:
    """
    Return asyncpg connect_args derived from the original URL.

    Neon requires SSL; asyncpg expects ssl='require' (or True), not sslmode=require.
    """
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=False)
    sslmode_values = query.get("sslmode", [])
    sslmode = sslmode_values[0].lower() if sslmode_values else None

    if sslmode in _SSL_REQUIRED_MODES:
        return {"ssl": "require"}

    # Neon hostnames always require TLS even if sslmode is omitted from the URL
    hostname = (parsed.hostname or "").lower()
    if "neon.tech" in hostname:
        return {"ssl": "require"}

    return {}


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

    @property
    def database_connect_args(self) -> dict:
        return database_connect_args(self.database_url)

    default_page_limit: int = 20
    max_page_limit: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()


def log_database_config(settings: Settings) -> None:
    """Log normalized database URL (password masked) at startup."""
    logger.info(
        "Database config: url=%s connect_args=%s",
        mask_database_url(settings.async_database_url),
        settings.database_connect_args or "{}",
    )
