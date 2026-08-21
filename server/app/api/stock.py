"""Текущие остатки по складам (экран «Склад»)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Item, Stock, Unit, User, Warehouse
from ..schemas.documents import StockPageOut, StockRowOut
from ..security import get_current_user

router = APIRouter(tags=["Остатки"])


@router.get("/stock", response_model=StockPageOut)
def list_stock(
    warehouse_id: int | None = None,
    q: str | None = Query(default=None, description="Поиск: наименование, артикул, штрих-код"),
    below_min_only: bool = Query(default=False, description="Только позиции ниже минимума"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Остатки по позициям×склады (только активные товары, остаток ≠ 0 не фильтруется)."""
    stmt = (
        select(
            Stock.item_id,
            Item.name.label("item_name"),
            Item.sku,
            Item.unit_id,
            Item.min_qty,
            Item.cost_price,
            Stock.warehouse_id,
            Warehouse.name.label("warehouse_name"),
            Stock.qty,
            Stock.reserved_qty,
        )
        .join(Item, Item.id == Stock.item_id)
        .join(Warehouse, Warehouse.id == Stock.warehouse_id)
        .where(Item.active == True)  # noqa: E712
    )
    if warehouse_id:
        stmt = stmt.where(Stock.warehouse_id == warehouse_id)
    if q:
        q = q.strip()
        ql = q.lower()
        stmt = stmt.where(
            func.ci_lower(Item.name).like(f"%{ql}%")
            | func.ci_lower(Item.sku).like(f"%{ql}%")
            | Item.sku == q
            | Item.barcode == q
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows_raw = db.execute(
        stmt.order_by(Item.name, Warehouse.name).offset((page - 1) * size).limit(size)
    ).all()

    # Ед. изм. подгружаем одним запросом (малая таблица)
    units = {u.id: u.name for u in db.scalars(select(Unit)).all()}

    rows: list[StockRowOut] = []
    for r in rows_raw:
        qty = float(r.qty or 0)
        below = qty < float(r.min_qty or 0)
        if below_min_only and not below:
            continue
        rows.append(StockRowOut(
            item_id=r.item_id, item_name=r.item_name, sku=r.sku,
            unit_name=units.get(r.unit_id),
            warehouse_id=r.warehouse_id, warehouse_name=r.warehouse_name,
            qty=qty, reserved_qty=float(r.reserved_qty or 0),
            cost_price=float(r.cost_price or 0),
            sum_cost=round(qty * float(r.cost_price or 0), 2),
            min_qty=float(r.min_qty or 0),
            below_min=below,
        ))
    return StockPageOut(rows=rows, total=total)
