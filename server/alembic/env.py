"""Alembic env: миграции модели «Склад ПРО»."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import config
from app.db import Base
import app.models  # noqa: F401 — регистрация всех моделей

config_ = context.config
if config_.config_file_name is not None:
    fileConfig(config_.config_file_name)

config_.set_main_option("sqlalchemy.url", config.DATABASE_URL)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # особенности SQLite
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config_.get_section(config_.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
