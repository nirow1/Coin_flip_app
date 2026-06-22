import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from logging.config import fileConfig
import asyncio

from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool

from alembic import context

from Backend.db import Base
from Backend.config import settings

# Import all models so they register with Base.metadata.
# Without these imports, Python never executes the class definitions
# and the tables are never registered → autogenerate would see an empty schema.

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from our settings so we don't have to hardcode
# credentials in alembic.ini.
#
# Option A (this approach): read DATABASE_URL from settings → single source of truth,
#   credentials stay in .env only.
# Option B: hardcode the URL directly in alembic.ini → works but credentials in two places.
# Option C: read from environment variable in alembic.ini using %(DATABASE_URL)s syntax →
#   possible but less flexible than reading from settings.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Offline mode: generates SQL migration scripts without connecting to the DB.
    Useful when you want to review the SQL before applying it, or when the DB
    is not accessible (e.g. on a CI server that has no DB).
    Run with: alembic upgrade head --sql
    """
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
    """
    Sync callback passed to connection.run_sync().
    Alembic's context.configure() and context.run_migrations() are synchronous,
    so they must be called inside run_sync() which bridges async → sync.
    """
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Creates an async engine and runs migrations through it.
    We chose async (asyncpg) here instead of sync (psycopg2) because:
      - Our App already uses asyncpg → no extra dependency needed.
      - psycopg2 wheels are not always available for newer Python versions (e.g. 3.14).
      - async_engine_from_config reads the same sqlalchemy.url we set above.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # NullPool: no connection reuse – safe for short-lived migration runs
    )

    async with connectable.connect() as connection:
        # run_sync bridges async connection → sync Alembic API
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Online mode: connects to the DB and applies migrations directly.
    asyncio.run() starts a fresh event loop for the migration run.
    This is the standard pattern for async Alembic with SQLAlchemy 2.0+.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
