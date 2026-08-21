"""Схемы справочников: товары, ед. изм, категории, контрагенты, склады."""
from datetime import datetime

from pydantic import BaseModel, Field


# ---------- Единицы измерения ----------
class UnitIn(BaseModel):
    name: str = Field(min_length=1, max_length=30)


class UnitOut(UnitIn):
    id: int
    model_config = {"from_attributes": True}


# ---------- Категории ----------
class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: int | None = None


class CategoryOut(CategoryIn):
    id: int
    model_config = {"from_attributes": True}


# ---------- Товары (Номенклатура) ----------
class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sku: str = Field(min_length=1, max_length=50)
    barcode: str | None = Field(default=None, max_length=50)
    unit_id: int
    category_id: int | None = None
    min_qty: float = 0
    cost_price: float = 0
    sale_price: float = 0
    default_partner_id: int | None = None
    notes: str | None = None
    active: bool = True


class ItemOut(ItemIn):
    id: int
    unit_name: str | None = None
    category_name: str | None = None
    default_partner_name: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ItemBaseRef(BaseModel):
    """Компактный вариант для выпадающих списков."""
    id: int
    name: str
    sku: str
    unit_name: str | None = None
    cost_price: float = 0
    sale_price: float = 0
    model_config = {"from_attributes": True}


# ---------- Контрагенты (Поставщики) ----------
class PartnerIn(BaseModel):
    kind: str = Field(default="supplier", pattern="^(supplier|customer|both)$")
    full_name: str = Field(min_length=1, max_length=200)
    short_name: str | None = None
    legal_address: str | None = None
    postal_address: str | None = None
    phone: str | None = None
    email: str | None = None
    inn: str | None = None
    ogrn: str | None = None
    notes: str | None = None
    active: bool = True


class PartnerOut(PartnerIn):
    id: int
    model_config = {"from_attributes": True}


# ---------- Склады ----------
class WarehouseIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    active: bool = True


class WarehouseOut(WarehouseIn):
    id: int
    model_config = {"from_attributes": True}


# ---------- Список с пагинацией ----------
class PageOut(BaseModel):
    items: list[ItemOut]
    total: int


# ---------- Карточка предприятия ----------
class CompanyOut(BaseModel):
    id: int
    full_name: str | None = None
    short_name: str | None = None
    legal_address: str | None = None
    postal_address: str | None = None
    phone: str | None = None
    email: str | None = None
    inn_kpp: str | None = None
    ogrn: str | None = None
    director: str | None = None
    bank: str | None = None
    bik: str | None = None
    account: str | None = None
    corr_account: str | None = None
    model_config = {"from_attributes": True}
