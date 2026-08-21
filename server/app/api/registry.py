"""Реестры: построчный журнал проведённых документов.

В 7.1 — отдельные листы-журналы ReestrPrihod / ReestrRashod / ReestrSpis
(Дата, Наименование, Артикул, Категория, Кол-во, Ед. изм, …).
Здесь: один общий источник — строки документов со статусом «проведён».
"""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    DOC_IN, DOC_OUT, DOC_TRANSFER, DOC_WRITEOFF, ST_POSTED,
    Category, Document, DocumentItem, Item, Partner, Unit, User, Warehouse,
)
from ..schemas.documents import JournalRowOut, RegistryPageOut
from ..security import get_current_user

router = APIRouter(tags=["Реестры"])

REGISTRY_TYPES = {"in": DOC_IN, "out": DOC_OUT, "writeoff": DOC_WRITEOFF, "transfer": DOC_TRANSFER}


@router.get("/registry/{rtype}", response_model=RegistryPageOut)
def list_registry(
    rtype: Literal["in", "out", "writeoff", "transfer"],
    date_from: date | None = None,
    date_to: date | None = None,
    partner_id: int | None = None,
    q: str | None = Query(default=None, description="Поиск: наименование, артикул, номер, накладная"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = (
        select(Document, DocumentItem, Item)
        .join(DocumentItem, DocumentItem.doc_id == Document.id)
        .join(Item, Item.id == DocumentItem.item_id)
        .where(Document.type == REGISTRY_TYPES[rtype])
        .where(Document.status == ST_POSTED)
    )
    if date_from:
        stmt = stmt.where(Document.date >= date_from)
    if date_to:
        stmt = stmt.where(Document.date <= date_to)
    if partner_id:
        stmt = stmt.where(Document.partner_id == partner_id)
    if q:
        ql = q.lower()
        stmt = stmt.where(
            func.ci_lower(Item.name).like(f"%{ql}%")
            | Item.sku.like(f"%{ql}%")
            | func.ci_lower(Document.number).like(f"%{ql}%")
            | func.ci_lower(Document.doc_ref).like(f"%{ql}%")
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows_raw = db.execute(
        stmt.order_by(Document.date.desc(), Document.id.desc(), DocumentItem.id)
        .offset((page - 1) * size).limit(size)
    ).all()

    # Справочные названия одним запросом на таблицу (малые справочники)
    warehouses = {w.id: w.name for w in db.scalars(select(Warehouse)).all()}
    partners = {p.id: p.full_name for p in db.scalars(select(Partner)).all()}
    categories = {c.id: c.name for c in db.scalars(select(Category)).all()}
    units = {u.id: u.name for u in db.scalars(select(Unit)).all()}

    rows: list[JournalRowOut] = []
    for doc, li, item in rows_raw:
        rows.append(JournalRowOut(
            doc_id=doc.id, doc_number=doc.number, date=doc.date,
            item_id=item.id, item_name=item.name, sku=item.sku,
            category_name=categories.get(item.category_id),
            qty=float(li.qty or 0), unit_name=units.get(item.unit_id),
            partner_name=partners.get(doc.partner_id), doc_ref=doc.doc_ref,
            out_by_name=doc.out_by.full_name if doc.out_by else None,
            received_by=doc.received_by, reason=doc.reason,
            warehouse_name=warehouses.get(li.warehouse_to_id or li.warehouse_from_id or doc.warehouse_id),
            warehouse_from_name=warehouses.get(li.warehouse_from_id),
            warehouse_to_name=warehouses.get(li.warehouse_to_id),
            note=li.note,
        ))
    return RegistryPageOut(rows=rows, total=total)
