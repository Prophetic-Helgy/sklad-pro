"""Пользователи, карточка предприятия, аудит, настройки."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class User(Base):
    """Сотрудник / пользователь (вместо таблицы Sotrud с паролем в открытом виде)."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)  # Логин
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)   # Ф.И.О.
    role: Mapped[str] = mapped_column(String(10), default="user", nullable=False)  # admin | user
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Company(Base):
    """Карточка предприятия (одна строка, id=1; как в листе «Админ» 7.1)."""
    __tablename__ = "company"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)        # Полное наименование
    short_name: Mapped[str | None] = mapped_column(String(100), nullable=True)       # Сокращенное
    legal_address: Mapped[str | None] = mapped_column(String(255), nullable=True)    # Юридический адрес
    postal_address: Mapped[str | None] = mapped_column(String(255), nullable=True)   # Почтовый адрес
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)             # Телефон/факс
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    inn_kpp: Mapped[str | None] = mapped_column(String(30), nullable=True)           # ИНН/КПП
    ogrn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    director: Mapped[str | None] = mapped_column(String(100), nullable=True)         # Руководитель
    bank: Mapped[str | None] = mapped_column(String(150), nullable=True)             # Банк
    bik: Mapped[str | None] = mapped_column(String(20), nullable=True)               # БИК
    account: Mapped[str | None] = mapped_column(String(30), nullable=True)           # Расчетный счет
    corr_account: Mapped[str | None] = mapped_column(String(30), nullable=True)      # Корреспондентский счет


class AuditLog(Base):
    """Журнал изменений (аудит): кто, когда, что."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(30), index=True, nullable=False)  # create | update | delete | post | cancel | login | ...
    entity: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # items | documents | ...
    entity_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    changes: Mapped[str | None] = mapped_column(Text, nullable=True)               # JSON-снимок изменений


class Setting(Base):
    """Настройки приложения (ключ-значение)."""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
