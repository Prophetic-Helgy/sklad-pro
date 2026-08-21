"""Схемы раздела «Админ»: предприятие, пользователи, настройки, аудит."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CompanyIn(BaseModel):
    """Карточка предприятия (все поля необязательны — обновляем то, что прислали)."""

    full_name: str | None = Field(default=None, max_length=200)
    short_name: str | None = Field(default=None, max_length=100)
    legal_address: str | None = Field(default=None, max_length=255)
    postal_address: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=100)
    inn_kpp: str | None = Field(default=None, max_length=30)
    ogrn: str | None = Field(default=None, max_length=20)
    director: str | None = Field(default=None, max_length=100)
    bank: str | None = Field(default=None, max_length=150)
    bik: str | None = Field(default=None, max_length=20)
    account: str | None = Field(default=None, max_length=30)
    corr_account: str | None = Field(default=None, max_length=30)


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str | None
    role: str
    active: bool

    model_config = {"from_attributes": True}


class UserIn(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=4, max_length=100)
    full_name: str | None = Field(default=None, max_length=100)
    role: Literal["admin", "user"] = "user"


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=100)
    role: Literal["admin", "user"] | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=4, max_length=100)


class SettingOut(BaseModel):
    key: str
    value: str


class SettingUpdate(BaseModel):
    key: str
    value: str


class AuditRowOut(BaseModel):
    id: int
    ts: datetime
    user_id: int | None
    username: str | None
    action: str
    entity: str
    entity_id: str | None
    changes: str | None


class AuditPageOut(BaseModel):
    rows: list[AuditRowOut]
    total: int
