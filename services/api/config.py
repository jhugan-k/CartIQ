"""Application settings.

pydantic-settings reads environment variables (and the .env file) into a single
typed object. If a required variable is missing or the wrong type, the app
crashes on startup with a clear error instead of failing mysteriously later.
"""

from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# libpq (psql, psycopg) understands these connection params; asyncpg does not,
# and raises TypeError on any connect() kwarg it doesn't recognise. Neon and
# Supabase hand out URLs with them appended, so strip them and re-express the
# intent through `db_connect_args` below.
_LIBPQ_ONLY_PARAMS = {"sslmode", "channel_binding"}
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", ""}


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

    # --- Daily spend caps (paid tier) ---
    # Enforced across ALL users combined, because per-user rate limits cap
    # abuse, not cost. Both reset at midnight UTC. Set either to 0 to switch
    # that capability off completely.
    #
    # 150 grounded searches/day keeps us inside the 5,000/month that Google
    # includes free (5000/31 is about 161); past that it is $14 per 1,000.
    daily_grounded_searches: int = 150
    # 500 generateContent calls/day. At roughly 4K input + 500 output tokens
    # each on flash-lite paid rates ($0.30/$2.50 per 1M), that caps token spend
    # near $1.25/day, and covers about 125 chats at 4 calls per chat.
    daily_gemini_requests: int = 500
    # The counters live in Redis. If Redis is unreachable we refuse chat rather
    # than allow unmetered spend — set true to prefer availability over the
    # budget guarantee.
    budget_fail_open: bool = False

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
        """Make any managed-Postgres URL usable by our asyncpg engine.

        Three fixes, so the string you copy out of a provider's dashboard works
        unedited both locally and in prod:
        1. Strip surrounding whitespace — pasting into a web env-var field very
           easily appends a newline, which ends up inside the last query param.
        2. Rewrite `postgres://` / `postgresql://` to the asyncpg driver.
        3. Drop libpq-only params (`sslmode`, `channel_binding`) that asyncpg
           rejects; TLS is re-applied via `db_connect_args`.
        """
        v = v.strip()
        if v.startswith("postgres://"):
            v = "postgresql+asyncpg://" + v[len("postgres://") :]
        elif v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://") :]

        parts = urlsplit(v)
        if parts.query:
            kept = [
                (key, val)
                for key, val in parse_qsl(parts.query, keep_blank_values=True)
                if key.lower() not in _LIBPQ_ONLY_PARAMS
            ]
            v = urlunsplit(parts._replace(query=urlencode(kept)))
        return v

    @property
    def db_connect_args(self) -> dict[str, object]:
        """Extra kwargs handed to `asyncpg.connect()`, chosen from the DB host.

        Managed Postgres requires TLS, but the local Docker Postgres doesn't
        speak it, so SSL is enabled only for remote hosts. Being explicit also
        beats asyncpg's `prefer` default, which silently falls back to plaintext.
        """
        host = (urlsplit(self.database_url).hostname or "").lower()
        if host in _LOCAL_HOSTS:
            return {}
        return {
            "ssl": "require",
            # Neon's pooled ("-pooler") host is PgBouncer in transaction mode,
            # which breaks asyncpg's prepared-statement cache. Disabling the
            # cache keeps either endpoint working.
            "statement_cache_size": 0,
        }

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS_ORIGINS is a comma-separated string in env; expose it as a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file is read once and the same object is shared."""
    return Settings()


settings = get_settings()
