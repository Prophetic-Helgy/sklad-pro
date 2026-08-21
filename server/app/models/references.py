"""Справочники: единицы измерения, категории, товары, контрагенты, склады."""
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class Unit(Base):
    """Единицы измерения (шт, кг, м и т.п.)."""
    __tablename__ = "units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)


class Category(Base):
    """Категории товаров (иерархия — опциональный родитель)."""
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)

    parent: Mapped["Category | None"] = relationship("Category", remote_side=[id], back_populates="children")
    children: Mapped[list["Category"]] = relationship("Category", back_populates="parent")


class Item(Base):
    """Товар (номенклатура).

    Наименование — первичная точка входа (как в Excel 7.1),
    но теперь артикул и штрих-код обязательны к вводу при создании,
    и все три поля уникальны.
    """
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    sku: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(50), unique=True, index=True, nullable=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    # Минимальный остаток (контроль запаса)
    min_qty: Mapped[float] = mapped_column(Numeric(18, 3), default=0, nullable=False)
    # Финансы (в Excel 7.1 не было — добавляем)
    cost_price: Mapped[float] = mapped_column(Numeric(18, 2), default=0, nullable=False)  # себестоимость
    sale_price: Mapped[float] = mapped_column(Numeric(18, 2), default=0, nullable=False)   # цена продажи
    # Поставщик по умолчанию (как «Поставщик» в номенклатуре 7.1)
    default_partner_id: Mapped[int | None] = mapped_column(ForeignKey("partners.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    unit: Mapped[Unit] = relationship(lazy="joined")
    category: Mapped["Category | None"] = relationship(lazy="joined")
    default_partner: Mapped["Partner | None"] = relationship(lazy="noload")

    @property
    def unit_name(self) -> str | None:
        return self.unit.name if self.unit else None

    @property
    def category_name(self) -> str | None:
        return self.category.name if self.category else None

    @property
    def default_partner_name(self) -> str | None:
        return self.default_partner.full_name if self.default_partner else None


class Partner(Base):
    """Контрагент: поставщик и/или покупатель (поля 1-в-1 со старым листом «Поставщики»)."""
    __tablename__ = "partners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), default="supplier", nullable=False)  # supplier | customer | both
    full_name: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    legal_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    postal_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)   # Тел/факс
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    inn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ogrn: Mapped[str | None] = mapped_column(String(20), nullable=True)    # ОГРН/ОГРНИП
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Warehouse(Base):
    """Склад / место хранения (в Excel 7.1 был один глобальный остаток)."""
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
