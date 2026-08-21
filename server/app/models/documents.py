"""Документы движения: приход, расход, списание, перемещение, инвентаризация."""
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base

if TYPE_CHECKING:
    from .references import Item, Partner, Warehouse
    from .users import User
    from .users import User

# Типы документов
DOC_IN = "in"           # Приход (поступление)
DOC_OUT = "out"         # Расход (отгрузка / отпуск)
DOC_WRITEOFF = "writeoff"  # Списание
DOC_TRANSFER = "transfer"  # Перемещение между складами
DOC_INVENTORY = "inventory"  # Инвентаризация

DOC_TYPES = (DOC_IN, DOC_OUT, DOC_WRITEOFF, DOC_TRANSFER, DOC_INVENTORY)

# Статусы
ST_DRAFT = "draft"        # Черновик
ST_POSTED = "posted"      # Проведён
ST_CANCELLED = "cancelled"  # Отменён (с обратным применением)

# Префиксы номеров (терминология 7.1)
DOC_NUMBER_PREFIX = {
    DOC_IN: "ПРИХ",
    DOC_OUT: "РАСХ",
    DOC_WRITEOFF: "СПИС",
    DOC_TRANSFER: "ПЕРЕМ",
    DOC_INVENTORY: "ИНВ",
}


class Document(Base):
    """Документ движения товаров."""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(12), index=True, nullable=False)
    # Номер назначается при проведении («Записать» в 7.1); у черновика — NULL.
    number: Mapped[str | None] = mapped_column(String(30), unique=True, index=True, nullable=True)  # ПРИХ-2026-0001
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(10), default=ST_DRAFT, index=True, nullable=False)

    # Шапка (соответствие по полям с 7.1)
    partner_id: Mapped[int | None] = mapped_column(ForeignKey("partners.id"), nullable=True)   # Поставщик
    doc_ref: Mapped[str | None] = mapped_column(String(50), nullable=True)                     # Накладная (№)
    out_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)       # Отпустил (сотрудник)
    received_by: Mapped[str | None] = mapped_column(String(200), nullable=True)                # Получил (получатель)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)                     # Причина списания
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)  # Склад (инвентаризация)
    source_doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)  # Создан на основании
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)                             # Комментарий

    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    items: Mapped[list["DocumentItem"]] = relationship(
        back_populates="doc", cascade="all, delete-orphan", order_by="DocumentItem.id"
    )
    inventory_results: Mapped[list["InventoryResult"]] = relationship(
        back_populates="doc", cascade="all, delete-orphan"
    )
    partner: Mapped["Partner | None"] = relationship(lazy="joined")
    warehouse: Mapped["Warehouse | None"] = relationship(lazy="joined")
    out_by: Mapped["User | None"] = relationship(lazy="joined", foreign_keys=[out_by_id])

    # ---------- Свойства-имена (для вывода в API) ----------
    @property
    def partner_name(self) -> str | None:
        return self.partner.full_name if self.partner else None

    @property
    def warehouse_name(self) -> str | None:
        return self.warehouse.name if self.warehouse else None

    @property
    def out_by_name(self) -> str | None:
        return self.out_by.full_name if self.out_by else None

    # Короткое имя для API (schema DocumentOut.results)
    @property
    def results(self) -> list["InventoryResult"]:
        return self.inventory_results


class DocNumber(Base):
    """Счётчик нумерации документов по типу и году (гарантирует последовательность)."""
    __tablename__ = "doc_numbers"

    type: Mapped[str] = mapped_column(String(12), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DocumentItem(Base):
    """Строка документа (позиция).

    Для инвентаризации строки НЕ используются — там InventoryResult.
    """
    __tablename__ = "document_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False, index=True)
    # Перемещение: warehouse_from → warehouse_to.
    # Приход: warehouse_to. Расход/списание: warehouse_from.
    warehouse_from_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    warehouse_to_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    qty: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)  # цена/себестоимость строки
    # Снапшот ед. изм. на момент проведения (история не искажается при смене ед. изм. товара)
    unit_snapshot: Mapped[str | None] = mapped_column(String(30), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    doc: Mapped[Document] = relationship(back_populates="items")
    item: Mapped["Item"] = relationship(lazy="joined")
    warehouse_from: Mapped["Warehouse | None"] = relationship(lazy="joined", foreign_keys=[warehouse_from_id])
    warehouse_to: Mapped["Warehouse | None"] = relationship(lazy="joined", foreign_keys=[warehouse_to_id])

    # ---------- Свойства-имена (для вывода в API) ----------
    @property
    def item_name(self) -> str:
        return self.item.name

    @property
    def unit_name(self) -> str | None:
        return self.item.unit_name if self.item else None

    @property
    def warehouse_from_name(self) -> str | None:
        return self.warehouse_from.name if self.warehouse_from else None

    @property
    def warehouse_to_name(self) -> str | None:
        return self.warehouse_to.name if self.warehouse_to else None


class InventoryResult(Base):
    """Результат инвентаризации по позиции (подсчёт и разница)."""
    __tablename__ = "inventory_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False, index=True)
    counted_qty: Mapped[float] = mapped_column(Numeric(18, 3), nullable=False)   # фактически подсчитано
    diff_qty: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)  # разница (заполняется при проведении)

    doc: Mapped[Document] = relationship(back_populates="inventory_results")
    item: Mapped["Item"] = relationship(lazy="joined")

    # ---------- Свойства-имена (для вывода в API) ----------
    @property
    def item_name(self) -> str:
        return self.item.name

    @property
    def unit_name(self) -> str | None:
        return self.item.unit_name if self.item else None
