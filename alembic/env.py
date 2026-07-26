"""Alembic migration environment.

URL and metadata come from the application, so migrations always match
the ORM models and read the same .env as the app.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import settings
from app.db.base import Base

# Import the model registry so every table is registered on Base.metadata.
import app.models  # noqa: F401

config = context.config

# NOTE: the DB URL comes straight from app settings (below), NOT via
# config.set_main_option — the URL-encoded password contains '%', which
# ConfigParser would try to interpret as interpolation syntax.

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        settings.DATABASE_URL, poolclass=pool.NullPool, future=True,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
