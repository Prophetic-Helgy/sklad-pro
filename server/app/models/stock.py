"""Текущие остатки (товар × склад)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class Stock(Base):
    """Остаток конкретного товара на конкретном складе.

    qty          — фактический остаток
    reserved_qty — зарезервированное количество (доступно = qty - reserved_qty)
    """
    __tablename__ = "stock"
    __table_args__ = (UniqueConstraint("item_id", "warehouse_id", name="uq_stock_item_warehouse"),)

    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), primary_key=True)
    qty: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    reserved_qty: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
