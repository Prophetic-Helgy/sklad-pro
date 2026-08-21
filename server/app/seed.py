"""Начальное заполнение БД (идемпотентно): администратор, основной склад,
базовые единицы измерения, настройки по умолчанию, карточка предприятия.

Запуск:  python seed.py
"""
from .db import Base, SessionLocal, engine
from .models import Company, Item, Setting, Stock, Unit, User, Warehouse
from .security import hash_password

# Настройки по умолчанию (ключ -> значение)
DEFAULT_SETTINGS = {
    "allow_negative_stock": "false",   # запрет отрицательных остатков
}

DEFAULT_UNITS = ["шт", "кг", "г", "л", "м", "уп", "коробка", "набор", "комплект", "партия"]


def seed():
    Base.metadata.create_all(engine)  # в dev; в продаксте — alembic upgrade head
    db = SessionLocal()
    try:
        # Администратор (пароль: 1234 — сменить после первого входа)
        if db.query(User).count() == 0:
            db.add(User(username="admin", password_hash=hash_password("1234"),
                        full_name="Администратор", role="admin"))

        # Основной склад + настройка default_warehouse_id
        if db.query(Warehouse).count() == 0:
            wh = Warehouse(name="Основной")
            db.add(wh)
            db.flush()
        else:
            wh = db.query(Warehouse).first()
        setting = db.get(Setting, "default_warehouse_id")
        if setting is None:
            db.add(Setting(key="default_warehouse_id", value=str(wh.id)))
        else:
            setting.value = str(wh.id)

        # Базовые единицы измерения
        existing = {u.name for u in db.query(Unit).all()}
        for name in DEFAULT_UNITS:
            if name not in existing:
                db.add(Unit(name=name))

        # Настройки по умолчанию
        for key, value in DEFAULT_SETTINGS.items():
            if db.get(Setting, key) is None:
                db.add(Setting(key=key, value=value))

        # Карточка предприятия (одна строка)
        if db.get(Company, 1) is None:
            db.add(Company(id=1))

        db.commit()
        print("Seed выполнен: admin/1234, склад «Основной», единицы измерения, настройки.")
    finally:
        db.close()


if __name__ == "__main__":
    from . import config  # noqa: F401 — инициализация путей
    seed()
