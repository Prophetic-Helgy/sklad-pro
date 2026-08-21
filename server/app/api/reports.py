"""Отчёты (Фаза 5): ОСВ/остатки, оборотка, движения, низкие остатки, ABC, оборачиваемость.

Все отчёты собираются в общую структуру `Report` — от неё строятся
и JSON-ответ (таблица на фронтенде), и экспорт в Excel/PDF.
"""
from datetime import date, timedelta
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    DOC_IN, DOC_INVENTORY, DOC_OUT, DOC_TRANSFER, DOC_WRITEOFF, ST_POSTED,
    Document, DocumentItem, InventoryResult, Item, Stock, User, Warehouse,
)
from ..report_export import Report, build_excel, build_pdf, col
from ..schemas.reports import ReportColumnOut, ReportOut
from ..security import get_current_user

router = APIRouter(tags=["Отчёты"])

ReportKind = Literal["balance", "movement", "turnover", "below_min", "abc", "turnover_speed"]

DOC_LABEL = {
    DOC_IN: "Приход", DOC_OUT: "Расход", DOC_WRITEOFF: "Списание",
    DOC_TRANSFER: "Перемещение", DOC_INVENTORY: "Инвентаризация",
}

KIND_TITLES = {
    "balance": "Остатки на дату (ОСВ)",
    "movement": "Отчёт по движениям",
    "turnover": "Оборотка (приход / расход / списание)",
    "below_min": "Низкие остатки (ниже минимума)",
    "abc": "ABC-анализ продаж",
    "turnover_speed": "Оборачиваемость запасов",
}


# ---------- Общие помощники ----------
def _period(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    today = date.today()
    df = date_from or date(today.year, 1, 1)
    dt = date_to or today
    if dt < df:
        dt = df
    return df, dt


def _items_map(db: Session) -> dict[int, Item]:
    return {i.id: i for i in db.scalars(select(Item)).all()}


def _warehouses_map(db: Session) -> dict[int, str]:
    return {w.id: w.name for w in db.scalars(select(Warehouse)).all()}


def _match_q(item: Item, q: str) -> bool:
    ql = q.lower()
    return ql in item.name.lower() or ql in item.sku.lower()


def _stock_as_of(db: Session, as_of: date, warehouse_id: int | None = None) -> dict[tuple[int, int], float]:
    """Остатки (item_id, warehouse_id) → кол-во после документов с датой ≤ as_of.

    Все изменения остатков проходят через проведение документов,
    поэтому баланс на дату — сумма строк документов по эту дату.
    """
    posted = (Document.status == ST_POSTED) & (Document.date <= as_of)

    def part(wh_col, sign: int, dtype: str):
        return (
            select(DocumentItem.item_id.label("item_id"), wh_col.label("warehouse_id"),
                   (DocumentItem.qty * sign).label("delta"))
            .select_from(DocumentItem)
            .join(Document, Document.id == DocumentItem.doc_id)
            .where(posted, Document.type == dtype, wh_col.isnot(None))
        )

    inv = (
        select(InventoryResult.item_id.label("item_id"), Document.warehouse_id.label("warehouse_id"),
               func.coalesce(InventoryResult.diff_qty, 0).label("delta"))
        .select_from(InventoryResult)
        .join(Document, Document.id == InventoryResult.doc_id)
        .where(posted, Document.type == DOC_INVENTORY, Document.warehouse_id.isnot(None))
    )
    stmt = part(DocumentItem.warehouse_to_id, 1, DOC_IN).union_all(
        part(DocumentItem.warehouse_from_id, -1, DOC_OUT),
        part(DocumentItem.warehouse_from_id, -1, DOC_WRITEOFF),
        part(DocumentItem.warehouse_from_id, -1, DOC_TRANSFER),
        part(DocumentItem.warehouse_to_id, 1, DOC_TRANSFER),
        inv,
    )
    sub = stmt.subquery()
    agg = (
        select(sub.c.item_id, sub.c.warehouse_id, func.sum(sub.c.delta).label("qty"))
        .group_by(sub.c.item_id, sub.c.warehouse_id)
    )
    if warehouse_id:
        agg = agg.where(stmt.c.warehouse_id == warehouse_id)
    return {(r.item_id, r.warehouse_id): float(r.qty or 0) for r in db.execute(agg).all()}


def _flow_out(db: Session, df: date, dt: date, warehouse_id: int | None) -> dict[int, float]:
    """Расход (out) по товарам за период — используется в оборотке и оборачиваемости."""
    s = (
        select(DocumentItem.item_id, func.sum(DocumentItem.qty))
        .select_from(DocumentItem)
        .join(Document, Document.id == DocumentItem.doc_id)
        .where(Document.status == ST_POSTED, Document.type == DOC_OUT,
               Document.date >= df, Document.date <= dt)
    )
    if warehouse_id:
        s = s.where(DocumentItem.warehouse_from_id == warehouse_id)
    return {r.item_id: float(r[1] or 0) for r in db.execute(s.group_by(DocumentItem.item_id)).all()}


# ---------- Отчёты ----------
def _build_balance(db: Session, as_of: date, warehouse_id: int | None, q: str | None) -> Report:
    stock = _stock_as_of(db, as_of, warehouse_id)
    items = _items_map(db)
    warehouses = _warehouses_map(db)
    rows: list = []
    order = sorted(stock.items(), key=lambda kv: (items[kv[0][0]].name, warehouses.get(kv[0][1] or 0, "")))
    for (item_id, wh_id), qty in order:
        item = items.get(item_id)
        if item is None:
            continue
        if abs(qty) < 1e-9 and not q:
            continue
        if q and not _match_q(item, q):
            continue
        cost = float(item.cost_price or 0)
        rows.append([item.name, item.sku, item.category_name, item.unit_name,
                     warehouses.get(wh_id), round(qty, 3), cost, round(qty * cost, 2)])
    totals = (["Итого", None, None, None, None, round(sum(r[5] for r in rows), 3),
               None, round(sum(r[7] for r in rows), 2)] if rows else None)
    return Report(
        title=KIND_TITLES["balance"], period=f"на {as_of:%d.%m.%Y}",
        columns=[
            col("item_name", "Наименование", width=280),
            col("sku", "Артикул", width=110),
            col("category_name", "Категория", width=120),
            col("unit_name", "Ед. изм.", width=70),
            col("warehouse_name", "Склад", width=120),
            col("qty", "Кол-во", "number", "right", 90),
            col("cost_price", "Себестоимость, руб.", "money", "right", 130),
            col("amount", "Сумма, руб.", "money", "right", 130),
        ],
        rows=rows, totals=totals,
    )


def _build_movement(db: Session, df: date, dt: date, doc_type: str,
                    warehouse_id: int | None, q: str | None) -> Report:
    types = [t for t in DOC_LABEL if doc_type == "all" or t == doc_type]
    with_lines = [t for t in types if t != DOC_INVENTORY]
    items = _items_map(db)
    warehouses = _warehouses_map(db)
    entries: list = []  # (date, doc_id, sub, row)

    if with_lines:
        stmt = (
            select(Document, DocumentItem)
            .join(DocumentItem, DocumentItem.doc_id == Document.id)
            .where(Document.status == ST_POSTED, Document.type.in_(with_lines),
                   Document.date >= df, Document.date <= dt)
        )
        if warehouse_id:
            stmt = stmt.where(DocumentItem.warehouse_from_id == warehouse_id
                              | DocumentItem.warehouse_to_id == warehouse_id
                              | Document.warehouse_id == warehouse_id)
        for doc, li in db.execute(stmt.order_by(Document.date, Document.id, DocumentItem.id)).all():
            row = _movement_row(doc, li, items.get(li.item_id), warehouses)
            if row is not None:
                entries.append((doc.date, doc.id, li.id, row))

    if DOC_INVENTORY in types:
        stmt = (
            select(Document, InventoryResult)
            .join(InventoryResult, InventoryResult.doc_id == Document.id)
            .where(Document.status == ST_POSTED, Document.type == DOC_INVENTORY,
                   Document.date >= df, Document.date <= dt)
        )
        if warehouse_id:
            stmt = stmt.where(Document.warehouse_id == warehouse_id)
        for doc, res in db.execute(stmt.order_by(Document.date, Document.id, InventoryResult.id)).all():
            row = _movement_row(doc, res, items.get(res.item_id), warehouses)
            if row is not None:
                entries.append((doc.date, doc.id, res.id, row))

    # Поиск (q) — на стороне Python, данных не много
    if q:
        entries = [e for e in entries if _movement_match(e[3], q)]
    entries.sort(key=lambda e: (e[0], e[1], e[2]))
    rows = [e[3] for e in entries]
    signed_sum = round(sum(r[7] for r in rows if r[7] is not None), 3)
    amount_sum = round(sum(r[9] for r in rows if r[9] is not None), 2)
    totals = (["Итого", None, None, None, None, None, None, signed_sum, None, amount_sum]
              if rows else None)
    return Report(
        title=KIND_TITLES["movement"], period=f"за {df:%d.%m.%Y} — {dt:%d.%m.%Y}",
        columns=[
            col("date", "Дата", width=100),
            col("number", "Номер", width=140),
            col("doc_type", "Тип", width=110),
            col("item_name", "Наименование", width=280),
            col("sku", "Артикул", width=110),
            col("wh_from", "Откуда", width=120),
            col("wh_to", "Куда", width=120),
            col("signed_qty", "Кол-во (±)", "number", "right", 100),
            col("price", "Цена, руб.", "money", "right", 110),
            col("amount", "Сумма, руб.", "money", "right", 120),
        ],
        rows=rows, totals=totals,
    )


def _movement_row(doc: Document, line, item: Item | None, wh: dict[int, str]) -> list | None:
    """Строка отчёта движений. line — DocumentItem или InventoryResult."""
    if item is None:
        return None
    price = float(line.price) if getattr(line, "price", None) is not None else None
    if doc.type == DOC_IN:
        signed = float(line.qty)
        row = [str(doc.date), doc.number, DOC_LABEL[doc.type], item.name, item.sku,
               None, wh.get(line.warehouse_to_id), signed, price,
               round(signed * price, 2) if price is not None else None]
    elif doc.type in (DOC_OUT, DOC_WRITEOFF):
        signed = -float(line.qty)
        row = [str(doc.date), doc.number, DOC_LABEL[doc.type], item.name, item.sku,
               wh.get(line.warehouse_from_id), None, signed, price,
               round(signed * price, 2) if price is not None else None]
    elif doc.type == DOC_TRANSFER:
        row = [str(doc.date), doc.number, DOC_LABEL[doc.type], item.name, item.sku,
               wh.get(line.warehouse_from_id), wh.get(line.warehouse_to_id), None, None, None]
    else:  # инвентаризация
        signed = float(getattr(line, "diff_qty", None) or 0)
        row = [str(doc.date), doc.number, DOC_LABEL[doc.type], item.name, item.sku,
               None, wh.get(doc.warehouse_id), signed, None, None]
    return row


def _movement_match(row: list, q: str) -> bool:
    ql = q.lower()
    return any(ql in str(v).lower() for v in (row[1], row[3], row[4]) if v)


def _build_turnover(db: Session, df: date, dt: date,
                    warehouse_id: int | None, q: str | None) -> Report:
    wh = warehouse_id

    def flow(dtype: str, wh_col):
        s = (
            select(DocumentItem.item_id, func.sum(DocumentItem.qty))
            .select_from(DocumentItem)
            .join(Document, Document.id == DocumentItem.doc_id)
            .where(Document.status == ST_POSTED, Document.type == dtype,
                   Document.date >= df, Document.date <= dt)
        )
        if wh:
            s = s.where(wh_col == wh)
        return {r.item_id: float(r[1] or 0) for r in db.execute(s.group_by(DocumentItem.item_id)).all()}

    received = flow(DOC_IN, DocumentItem.warehouse_to_id)
    shipped = flow(DOC_OUT, DocumentItem.warehouse_from_id)
    written = flow(DOC_WRITEOFF, DocumentItem.warehouse_from_id)
    corr = (
        select(InventoryResult.item_id, func.sum(func.coalesce(InventoryResult.diff_qty, 0)))
        .select_from(InventoryResult)
        .join(Document, Document.id == InventoryResult.doc_id)
        .where(Document.status == ST_POSTED, Document.type == DOC_INVENTORY,
               Document.date >= df, Document.date <= dt)
    )
    if wh:
        corr = corr.where(Document.warehouse_id == wh)
    corrected = {r.item_id: float(r[1] or 0) for r in db.execute(corr.group_by(InventoryResult.item_id)).all()}

    opening_map: dict[int, float] = {}
    for (item_id, _w), qty in _stock_as_of(db, df - timedelta(days=1), wh).items():
        opening_map[item_id] = opening_map.get(item_id, 0.0) + qty

    items = _items_map(db)
    item_ids = set(opening_map) | set(received) | set(shipped) | set(written) | set(corrected)
    rows: list = []
    for item_id in sorted(item_ids, key=lambda i: items[i].name):
        item = items.get(item_id)
        if item is None or (q and not _match_q(item, q)):
            continue
        o = opening_map.get(item_id, 0.0)
        rcv = received.get(item_id, 0.0)
        shp = shipped.get(item_id, 0.0)
        wrt = written.get(item_id, 0.0)
        cor = corrected.get(item_id, 0.0)
        closing = o + rcv - shp - wrt + cor
        rows.append([item.name, item.sku, item.category_name, item.unit_name,
                     round(o, 3), round(rcv, 3), round(shp, 3), round(wrt, 3), round(cor, 3),
                     round(closing, 3), round(closing * float(item.cost_price or 0), 2)])
    totals = None
    if rows:
        totals = ["Итого", None, None, None] + [round(sum(r[i] for r in rows), 3) for i in range(4, 10)] \
            + [round(sum(r[10] for r in rows), 2)]
    return Report(
        title=KIND_TITLES["turnover"], period=f"за {df:%d.%m.%Y} — {dt:%d.%m.%Y}",
        columns=[
            col("item_name", "Наименование", width=260),
            col("sku", "Артикул", width=100),
            col("category_name", "Категория", width=110),
            col("unit_name", "Ед. изм.", width=70),
            col("opening", "Остаток (нач)", "number", "right", 100),
            col("received", "Приход", "number", "right", 90),
            col("shipped", "Расход", "number", "right", 90),
            col("written", "Списание", "number", "right", 90),
            col("corrected", "Инвентаризация", "number", "right", 110),
            col("closing", "Остаток (кон)", "number", "right", 100),
            col("amount", "Сумма, руб.", "money", "right", 120),
        ],
        rows=rows, totals=totals,
    )


def _build_below_min(db: Session, warehouse_id: int | None, q: str | None) -> Report:
    s = select(Stock.item_id, func.sum(Stock.qty)).group_by(Stock.item_id)
    if warehouse_id:
        s = s.where(Stock.warehouse_id == warehouse_id)
    stock = {r.item_id: float(r[1] or 0) for r in db.execute(s).all()}
    items = _items_map(db)
    warehouses = _warehouses_map(db)
    rows: list = []
    for item in items.values():
        if not item.active or not item.min_qty:
            continue
        cur = stock.get(item.id, 0.0)
        if cur > float(item.min_qty):
            continue
        if q and not _match_q(item, q):
            continue
        rows.append([item.name, item.sku, item.unit_name,
                     warehouses.get(warehouse_id) if warehouse_id else "все склады",
                     float(item.min_qty), round(cur, 3), round(float(item.min_qty) - cur, 3)])
    rows.sort(key=lambda r: -r[6])
    totals = (["Итого", None, None, None, None, None, round(sum(r[6] for r in rows), 3)] if rows else None)
    return Report(
        title=KIND_TITLES["below_min"], period=None,
        columns=[
            col("item_name", "Наименование", width=280),
            col("sku", "Артикул", width=110),
            col("unit_name", "Ед. изм.", width=70),
            col("warehouse_name", "Склад", width=140),
            col("min_qty", "Мин. остаток", "number", "right", 100),
            col("current", "Текущий", "number", "right", 90),
            col("deficit", "Недостача", "number", "right", 90),
        ],
        rows=rows, totals=totals,
    )


def _build_abc(db: Session, df: date, dt: date) -> Report:
    s = (
        select(DocumentItem.item_id,
               func.sum(DocumentItem.qty),
               func.sum(func.coalesce(DocumentItem.price, Item.cost_price) * DocumentItem.qty))
        .select_from(DocumentItem)
        .join(Document, Document.id == DocumentItem.doc_id)
        .join(Item, Item.id == DocumentItem.item_id)
        .where(Document.status == ST_POSTED, Document.type == DOC_OUT,
               Document.date >= df, Document.date <= dt)
        .group_by(DocumentItem.item_id)
    )
    raw = {r.item_id: (float(r[1] or 0), float(r[2] or 0)) for r in db.execute(s).all()}
    items = _items_map(db)
    data = sorted(((iid, qty, amt) for iid, (qty, amt) in raw.items() if amt > 0 and items.get(iid)),
                  key=lambda t: -t[2])
    total = sum(t[2] for t in data) or 1.0
    rows: list = []
    cum = 0.0
    for iid, qty, amt in data:
        item = items[iid]
        share = amt / total * 100
        cum += share
        cls = "A" if cum <= 70 else ("B" if cum <= 90 else "C")
        rows.append([item.name, item.sku, round(qty, 3), round(amt, 2),
                     round(share, 1), round(cum, 1), cls])
    totals = (["Итого", None, round(sum(t[1] for t in data), 3), round(sum(t[2] for t in data), 2),
               None, None, None] if rows else None)
    return Report(
        title=KIND_TITLES["abc"], period=f"за {df:%d.%m.%Y} — {dt:%d.%m.%Y}",
        columns=[
            col("item_name", "Наименование", width=280),
            col("sku", "Артикул", width=110),
            col("qty_sold", "Продано, кол-во", "number", "right", 110),
            col("amount", "Сумма продаж, руб.", "money", "right", 130),
            col("share", "Доля, %", "percent", "right", 80),
            col("cum", "Наращ. доля, %", "percent", "right", 100),
            col("abc_class", "Класс", width=70),
        ],
        rows=rows, totals=totals,
    )


def _build_turnover_speed(db: Session, df: date, dt: date, warehouse_id: int | None) -> Report:
    opening_map: dict[int, float] = {}
    for (item_id, _w), qty in _stock_as_of(db, df - timedelta(days=1), warehouse_id).items():
        opening_map[item_id] = opening_map.get(item_id, 0.0) + qty
    closing_map: dict[int, float] = {}
    for (item_id, _w), qty in _stock_as_of(db, dt, warehouse_id).items():
        closing_map[item_id] = closing_map.get(item_id, 0.0) + qty
    shipped = _flow_out(db, df, dt, warehouse_id)
    days = max((dt - df).days, 1)

    items = _items_map(db)
    rows: list = []
    for item_id in sorted(set(opening_map) | set(closing_map) | set(shipped),
                          key=lambda i: items[i].name):
        item = items.get(item_id)
        if item is None:
            continue
        o = opening_map.get(item_id, 0.0)
        c = closing_map.get(item_id, 0.0)
        shp = shipped.get(item_id, 0.0)
        if o == 0 and c == 0 and shp == 0:
            continue
        avg = (o + c) / 2
        daily = shp / days
        dts = avg / daily if daily > 0 else None
        turn = days / dts if dts else None
        rows.append([item.name, item.sku, item.unit_name, round(avg, 3), round(shp, 3),
                     round(daily, 3) if daily else 0,
                     round(dts, 1) if dts is not None else None,
                     round(turn, 2) if turn is not None else None])
    totals = (["Итого", None, None, round(sum(r[3] for r in rows), 3), round(sum(r[4] for r in rows), 3),
               None, None, None] if rows else None)
    return Report(
        title=KIND_TITLES["turnover_speed"], period=f"за {df:%d.%m.%Y} — {dt:%d.%m.%Y}",
        columns=[
            col("item_name", "Наименование", width=280),
            col("sku", "Артикул", width=110),
            col("unit_name", "Ед. изм.", width=70),
            col("avg_balance", "Средний остаток", "number", "right", 110),
            col("shipped", "Расход за период", "number", "right", 110),
            col("daily", "Средний расход/день", "number", "right", 120),
            col("days_to_sell", "Дней реализации", "number", "right", 110),
            col("turnover", "Коэф. оборачиваемости", "number", "right", 130),
        ],
        rows=rows, totals=totals,
    )


def _build(db: Session, kind: str, date_from: date | None, date_to: date | None,
           as_of: date | None, warehouse_id: int | None, doc_type: str, q: str | None) -> Report:
    if kind == "balance":
        return _build_balance(db, as_of or date.today(), warehouse_id, q)
    df, dt = _period(date_from, date_to)
    if kind == "movement":
        return _build_movement(db, df, dt, doc_type, warehouse_id, q)
    if kind == "turnover":
        return _build_turnover(db, df, dt, warehouse_id, q)
    if kind == "below_min":
        return _build_below_min(db, warehouse_id, q)
    if kind == "abc":
        return _build_abc(db, df, dt)
    return _build_turnover_speed(db, df, dt, warehouse_id)


# ---------- HTTP ----------
@router.get("/reports/{kind}", response_model=ReportOut)
def get_report(
    kind: ReportKind,
    date_from: date | None = Query(default=None, description="Начало периода"),
    date_to: date | None = Query(default=None, description="Конец периода"),
    as_of: date | None = Query(default=None, description="Остатки на дату (для ОСВ)"),
    warehouse_id: int | None = None,
    doc_type: Literal["all", "in", "out", "writeoff", "transfer", "inventory"] = "all",
    q: str | None = Query(default=None, description="Поиск: наименование, артикул, номер"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rep = _build(db, kind, date_from, date_to, as_of, warehouse_id, doc_type, q)
    total = len(rep.rows)
    start = (page - 1) * size
    return ReportOut(
        title=rep.title, period=rep.period,
        columns=[ReportColumnOut(**c) for c in rep.columns],
        rows=rep.rows[start:start + size],
        totals=rep.totals, total=total,
    )


@router.get("/reports/{kind}/export")
def export_report(
    kind: ReportKind,
    fmt: Literal["excel", "pdf"] = "excel",
    date_from: date | None = None,
    date_to: date | None = None,
    as_of: date | None = None,
    warehouse_id: int | None = None,
    doc_type: Literal["all", "in", "out", "writeoff", "transfer", "inventory"] = "all",
    q: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Экспорт отчёта во внешний файл: ?fmt=excel (.xlsx) или ?fmt=pdf."""
    rep = _build(db, kind, date_from, date_to, as_of, warehouse_id, doc_type, q)
    if fmt == "excel":
        data, media, ext = build_excel(rep), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    else:
        data, media, ext = build_pdf(rep), "application/pdf", "pdf"
    name = f"{rep.title}" + (f" — {rep.period}" if rep.period else "") + f".{ext}"
    return Response(
        content=data, media_type=media,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"},
    )
