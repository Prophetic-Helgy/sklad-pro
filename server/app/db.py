"""Подключение к базе данных (SQLite, WAL-режим)."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from . import config


class Base(DeclarativeBase):
    """Базовый класс ORM-моделей."""


engine = create_engine(
    config.DATABASE_URL,
    echo=False,
    # Один файл базы может использовать несколько сессий FastAPI
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """WAL + блокировки: стабильная работа при одновременном доступе."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
    # Встроенные lower()/LIKE в SQLite не знают кириллицы (регистронезависимость
    # только для ASCII), поэтому регистрируем Python-функцию для поиска без учёта регистра.
    dbapi_connection.create_function(
        "ci_lower", 1, lambda s: s.lower() if s is not None else None
    )


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """Зависимость FastAPI: сессия на время запроса."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
