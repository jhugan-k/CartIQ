"""Application settings.

pydantic-settings reads environment variables (and the .env file) into a single
typed object. If a required variable is missing or the wrong type, the app
crashes on startup with a clear error instead of failing mysteriously later.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Database ---
    database_url: str

    # --- Cache ---
    redis_url: str
    cache_ttl_seconds: int = 1800  # 30 minutes

    # --- Auth ---
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # --- QuickCommerce API ---
    quickcommerce_api_key: str
    quickcommerce_base_url: str = "https://api.quickcommerceapi.com"
    # when true, the QC client returns canned data instead of calling the paid
    # API. Lets us build/test without spending credits (trial is expired).
    use_mock_qc: bool = True

    # --- Gemini (Part 8) ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-lite-latest"

    # --- CORS ---
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        """Managed Postgres (Render/Neon/Supabase) hands out `postgres://` or
        `postgresql://` URLs, but our async engine needs the asyncpg driver.
        Rewrite the scheme so the same DATABASE_URL works locally and in prod."""
        if v.startswith("postgres://"):
            return "postgresql+asyncpg://" + v[len("postgres://") :]
        if v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://") :]
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS_ORIGINS is a comma-separated string in env; expose it as a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file is read once and the same object is shared."""
    return Settings()


settings = get_settings()
