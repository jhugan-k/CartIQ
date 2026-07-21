"""Alembic environment — configured for CartIQ's async SQLAlchemy setup.

Two customizations over the stock template:
1. The database URL comes from our app settings (.env), not alembic.ini, so
   there is a single source of truth for the connection string.
2. Migrations run through the async asyncpg engine, bridged to Alembic's
   synchronous internals via `connection.run_sync`.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# --- Make the app package importable (env.py runs from services/api/) ---
from config import settings
from database import Base
import models  # noqa: F401  side-effect: registers all tables on Base.metadata

# Alembic Config object — access to values in alembic.ini.
config = context.config

# inject the real DB URL from settings, overriding the placeholder in the ini.
config.set_main_option("sqlalchemy.url", settings.database_url)

# Python logging setup from the ini file.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate compares this metadata against the live DB to detect changes.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection (`alembic upgrade --sql`)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Create an async engine and run migrations against a live connection."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # migrations are short CLI runs — no pool needed
    )
    async with connectable.connect() as connection:
        # run_sync bridges Alembic's sync migration code onto the async connection.
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
