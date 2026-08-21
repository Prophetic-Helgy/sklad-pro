"""Схемы документов: создание/редактирование (черновики) и вывод со строками."""
from datetime import date, datetime

from pydantic import BaseModel, Field


# ---------- Вход: строка документа ----------
class DocItemIn(BaseModel):
    item_id: int
    warehouse_from_id: int | None = None   # расход/списание/перемещение
    warehouse_to_id: int | None = None     # приход/перемещение
    qty: float = Field(gt=0)
    price: float | None = None
    note: str | None = None


class InventoryResultIn(BaseModel):
    item_id: int
    counted_qty: float = Field(ge=0)       # Остаток (факт)


# ---------- Вход: документ ----------
class DocumentIn(BaseModel):
    type: str = Field(pattern="^(in|out|writeoff|transfer|inventory)$")
    date: date
    partner_id: int | None = None
    doc_ref: str | None = Field(default=None, max_length=50)          # Накладная (№)
    out_by_id: int | None = None                                          # Отпустил
    received_by: str | None = Field(default=None, max_length=200)        # Получил
    reason: str | None = Field(default=None, max_length=255)             # Причина списания
    warehouse_id: int | None = None                                        # склад по умолчанию / инвентаризация
    source_doc_id: int | None = None                                       # создан на основании
    notes: str | None = None
    items: list[DocItemIn] = []
    results: list[InventoryResultIn] = []


# ---------- Вывод: строка ----------
class DocItemOut(BaseModel):
    id: int
    item_id: int
    item_name: str
    unit_name: str | None = None
    warehouse_from_id: int | None = None
    warehouse_from_name: str | None = None
    warehouse_to_id: int | None = None
    warehouse_to_name: str | None = None
    qty: float
    price: float | None = None
    note: str | None = None
    model_config = {"from_attributes": True}


class InventoryResultOut(BaseModel):
    id: int
    item_id: int
    item_name: str
    unit_name: str | None = None
    counted_qty: float
    diff_qty: float | None = None
    model_config = {"from_attributes": True}


# ---------- Вывод: документ ----------
class DocumentOut(BaseModel):
    id: int
    type: str
    number: str | None = None
    date: date
    status: str
    partner_id: int | None = None
    partner_name: str | None = None
    doc_ref: str | None = None
    out_by_id: int | None = None
    out_by_name: str | None = None
    received_by: str | None = None
    reason: str | None = None
    warehouse_id: int | None = None
    warehouse_name: str | None = None
    source_doc_id: int | None = None
    notes: str | None = None
    created_at: datetime | None = None
    posted_at: datetime | None = None
    items: list[DocItemOut] = []
    results: list[InventoryResultOut] = []
    model_config = {"from_attributes": True}


# ---------- Список ----------
class DocsPageOut(BaseModel):
    documents: list[DocumentOut]
    total: int


# ---------- Реестры (построчный журнал проведённых документов) ----------
class JournalRowOut(BaseModel):
    doc_id: int
    doc_number: str | None = None
    date: date
    item_id: int
    item_name: str
    sku: str
    category_name: str | None = None
    qty: float
    unit_name: str | None = None
    partner_name: str | None = None
    doc_ref: str | None = None
    out_by_name: str | None = None
    received_by: str | None = None
    reason: str | None = None
    warehouse_name: str | None = None            # склад операции (приход — «куда», расход/списание — «откуда»)
    warehouse_from_name: str | None = None
    warehouse_to_name: str | None = None
    note: str | None = None


class RegistryPageOut(BaseModel):
    rows: list[JournalRowOut]
    total: int


# ---------- Остатки ----------
class StockRowOut(BaseModel):
    item_id: int
    item_name: str
    sku: str
    unit_name: str | None = None
    warehouse_id: int
    warehouse_name: str
    qty: float
    reserved_qty: float = 0
    cost_price: float = 0
    sum_cost: float = 0            # qty * себестоимость
    min_qty: float = 0
    below_min: bool = False        # остаток ниже минимума (и > 0 не требуется)
    model_config = {"from_attributes": True}


class StockPageOut(BaseModel):
    rows: list[StockRowOut]
    total: int
