"""Alembic migration environment configuration.

Imports SQLModel metadata and all table models so Alembic can autogenerate
migrations. The database URL is overridden from app settings to keep a single
source of truth.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import SQLModel metadata and all models so Alembic can autogenerate migrations.
from sqlmodel import SQLModel  # noqa: E402
import app.models  # noqa: E402, F401 — ensures all table models are registered

target_metadata = SQLModel.metadata

# Override sqlalchemy.url from app settings so there's a single source of truth.
from app.config import settings  # noqa: E402

config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Offline mode generates SQL scripts without connecting to a database.
    This is useful for code review or when the database is not reachable.
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


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Online mode connects directly to the database and executes migrations
    against the live schema.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()