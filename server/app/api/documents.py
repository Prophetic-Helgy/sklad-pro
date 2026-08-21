"""Документы движения: черновики, проведение в остатки, отмена.

Логика соответствует 7.1: «Записать» = провести (назначается номер,
остатки обновляются, запись попадает в реестр). Черновик не влияет
на остатки. Отмена проведённого = обратное применение.
"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import core, posting
from ..db import get_db
from ..models import (
    DOC_IN, DOC_INVENTORY, DOC_OUT, DOC_TRANSFER, DOC_WRITEOFF,
    ST_DRAFT, ST_POSTED, ST_CANCELLED,
    Document, DocumentItem, InventoryResult, Item, Partner, User, Warehouse,
)
from ..schemas.documents import (
    DocItemIn, DocumentIn, DocumentOut, DocsPageOut, InventoryResultIn,
)
from ..security import get_current_user

router = APIRouter(tags=["Документы"])

DOC_TITLE = {
    DOC_IN: "Приход",
    DOC_OUT: "Расход",
    DOC_WRITEOFF: "Списание",
    DOC_TRANSFER: "Перемещение",
    DOC_INVENTORY: "Инвентаризация",
}


def _bad_request(msg: str):
    raise HTTPException(400, msg)


def _not_found(doc_id: int):
    raise HTTPException(404, "Документ не найден")


def _validate_and_build(db: Session, data: DocumentIn, doc: Document) -> None:
    """Проверки при создании/изменении: типы, наличие позиций, склады, товары."""
    title = DOC_TITLE[data.type]
    if data.type == DOC_INVENTORY:
        if not data.results:
            _bad_request("Инвентаризация: добавьте позиции подсчёта")
        if not data.warehouse_id:
            _bad_request("Инвентаризация: укажите склад")
        for r in data.results:
            if db.get(Item, r.item_id) is None:
                _bad_request(f"Товар №{r.item_id} не найден")
    else:
        if not data.items:
            _bad_request(f"{title}: добавьте хотя бы одну строку")
        for li in data.items:
            if db.get(Item, li.item_id) is None:
                _bad_request(f"Товар №{li.item_id} не найден")
            for wh_id in (li.warehouse_from_id, li.warehouse_to_id):
                if wh_id and db.get(Warehouse, wh_id) is None:
                    _bad_request(f"Склад №{wh_id} не найден")
            # Склад по умолчанию из шапки (как один «Склад» в документе 7.1)
            if data.warehouse_id:
                if data.type == DOC_IN and not li.warehouse_to_id:
                    li.warehouse_to_id = data.warehouse_id
                if data.type in (DOC_OUT, DOC_WRITEOFF) and not li.warehouse_from_id:
                    li.warehouse_from_id = data.warehouse_id
    if data.partner_id and db.get(Partner, data.partner_id) is None:
        _bad_request(f"Контрагент №{data.partner_id} не найден")
    if data.warehouse_id and db.get(Warehouse, data.warehouse_id) is None:
        _bad_request(f"Склад №{data.warehouse_id} не найден")


def _populate_lines(db: Session, doc: Document, data: DocumentIn) -> None:
    """Заполнить строки/результаты документа из схемы."""
    for old in list(doc.items):
        db.delete(old)
    for old in list(doc.inventory_results):
        db.delete(old)
    for li in data.items:
        item = db.get(Item, li.item_id)
        doc.items.append(
            DocumentItem(
                item_id=li.item_id,
                warehouse_from_id=li.warehouse_from_id,
                warehouse_to_id=li.warehouse_to_id,
                qty=li.qty,
                price=li.price,
                unit_snapshot=item.unit_name if item else None,
                note=li.note,
            )
        )
    for r in data.results:
        doc.inventory_results.append(
            InventoryResult(item_id=r.item_id, counted_qty=r.counted_qty, diff_qty=None)
        )


# ================= CRUD черновиков =================
@router.post("/documents", response_model=DocumentOut)
def create_document(data: DocumentIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = Document(
        type=data.type, number=None, date=data.date, status=ST_DRAFT,
        partner_id=data.partner_id, doc_ref=data.doc_ref, out_by_id=data.out_by_id,
        received_by=data.received_by, reason=data.reason, warehouse_id=data.warehouse_id,
        source_doc_id=data.source_doc_id, notes=data.notes, created_by=user.id,
    )
    db.add(doc)
    db.flush()
    _validate_and_build(db, data, doc)
    _populate_lines(db, doc, data)
    core.audit(db, user.id, "create", "documents", doc.id, {"type": data.type, "date": str(data.date)})
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/documents", response_model=DocsPageOut)
def list_documents(
    type: str | None = Query(default=None, pattern="^(in|out|writeoff|transfer|inventory)$"),
    status: str | None = Query(default=None, pattern="^(draft|posted|cancelled)$"),
    q: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Список документов с фильтрами (реестры фазы 4 используют тот же эндпоинт)."""
    stmt = select(Document)
    if type:
        stmt = stmt.where(Document.type == type)
    if status:
        stmt = stmt.where(Document.status == status)
    if date_from:
        stmt = stmt.where(Document.date >= date_from)
    if date_to:
        stmt = stmt.where(Document.date <= date_to)
    if q:
        q = q.strip()
        ql = q.lower()
        stmt = stmt.join(Partner, Document.partner_id == Partner.id, isouter=True).where(
            or_(
                Document.number.ilike(f"%{q}%"),
                Document.doc_ref.ilike(f"%{q}%"),
                func.ci_lower(Partner.full_name).like(f"%{ql}%"),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    docs = db.scalars(
        stmt.order_by(Document.created_at.desc(), Document.id.desc()).offset((page - 1) * size).limit(size)
    ).all()
    return DocsPageOut(documents=docs, total=total)


@router.get("/documents/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.get(Document, doc_id) or _not_found(doc_id)


@router.put("/documents/{doc_id}", response_model=DocumentOut)
def update_document(doc_id: int, data: DocumentIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = db.get(Document, doc_id) or _not_found(doc_id)
    if doc.status != ST_DRAFT:
        raise HTTPException(409, "Изменять можно только черновик")
    if doc.type != data.type:
        _bad_request("Тип документа изменить нельзя")
    doc.date = data.date
    doc.partner_id = data.partner_id
    doc.doc_ref = data.doc_ref
    doc.out_by_id = data.out_by_id
    doc.received_by = data.received_by
    doc.reason = data.reason
    doc.warehouse_id = data.warehouse_id
    doc.source_doc_id = data.source_doc_id
    doc.notes = data.notes
    _validate_and_build(db, data, doc)
    _populate_lines(db, doc, data)
    core.audit(db, user.id, "update", "documents", doc.id, {"type": data.type})
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = db.get(Document, doc_id) or _not_found(doc_id)
    if doc.status != ST_DRAFT:
        raise HTTPException(409, "Удалить можно только черновик — проведённый документ отменяется")
    db.delete(doc)
    core.audit(db, user.id, "delete", "documents", doc_id)
    db.commit()


# ================= Проведение / отмена =================
@router.post("/documents/{doc_id}/post", response_model=DocumentOut)
def post_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """«Записать» в 7.1: назначить номер, применить к остаткам, поместить в реестр."""
    doc = db.get(Document, doc_id) or _not_found(doc_id)
    if doc.status != ST_DRAFT:
        raise HTTPException(409, f"Документ уже {doc.status}: провести можно только черновик")
    try:
        if doc.type == DOC_INVENTORY:
            posting.fill_inventory_diffs(db, doc)
        posting.apply_doc(db, doc)
        doc.number = core.next_document_number(db, doc.type, doc.date.year)
        doc.status = ST_POSTED
        doc.posted_at = datetime.utcnow()
    except Exception:
        db.rollback()
        raise
    core.audit(db, user.id, "post", "documents", doc.id, {"number": doc.number})
    db.commit()
    db.refresh(doc)
    return doc


@router.post("/documents/{doc_id}/cancel", response_model=DocumentOut)
def cancel_document(doc_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Отмена проведённого: обратное применение к остаткам, статус «отменён»."""
    doc = db.get(Document, doc_id) or _not_found(doc_id)
    if doc.status != ST_POSTED:
        raise HTTPException(409, "Отменить можно только проведённый документ")
    try:
        posting.reverse_doc(db, doc)
        doc.status = ST_CANCELLED
    except Exception:
        db.rollback()
        raise
    core.audit(db, user.id, "cancel", "documents", doc.id, {"number": doc.number})
    db.commit()
    db.refresh(doc)
    return doc
