"""Alembic environment.

The URL comes from the application's own settings rather than alembic.ini, so
there is exactly one place a connection string is configured and no chance of
migrations running against a different database than the app.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from app.garage import models as _garage_models  # noqa: F401

# Imported for the side effect of registering the tables on Base.metadata.
# Without this, autogenerate sees no models and cheerfully proposes dropping
# every table the application depends on.
from app.identity import models as _identity_models  # noqa: F401
from app.models import Base
from app.settings import Settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = Settings()
if not settings.database_url:
    raise RuntimeError(
        "CMC_DATABASE_URL is not set. Migrations must never fall back to a "
        "default connection string — a silent default is how a migration ends "
        "up applied to the wrong database."
    )
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Detect column type changes, which autogenerate misses by default and
        # which are exactly the changes that silently corrupt data.
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
