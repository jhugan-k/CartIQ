"""Async database layer.

- `engine`     — manages the connection pool to PostgreSQL (via asyncpg).
- `Base`       — the parent class every ORM model inherits from; collects table
                 metadata so Alembic can autogenerate migrations.
- `get_db`     — FastAPI dependency that yields one session per request and
                 always closes it afterwards.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import settings

# one engine for the whole app. It holds a pool of reusable DB connections.
engine = create_async_engine(
    settings.database_url,
    echo=False,        # set True to log every SQL statement while debugging
    pool_pre_ping=True,  # checks a connection is alive before using it
)

# factory that produces AsyncSession objects (one per request).
# expire_on_commit=False keeps attributes accessible after commit, which avoids
# unexpected lazy-load queries in async code.
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Parent class for all ORM models."""


# hand each request its own database session and guarantee it's closed after.
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a session, close it when the request finishes."""
    async with SessionLocal() as session:
        yield session
