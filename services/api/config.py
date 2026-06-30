"""Application settings.

pydantic-settings reads environment variables (and the .env file) into a single
typed object. If a required variable is missing or the wrong type, the app
crashes on startup with a clear error instead of failing mysteriously later.
"""

from functools import lru_cache

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

    # --- Gemini (Part 8) ---
    gemini_api_key: str = ""

    # --- CORS ---
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS_ORIGINS is a comma-separated string in env; expose it as a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file is read once and the same object is shared."""
    return Settings()


settings = get_settings()
