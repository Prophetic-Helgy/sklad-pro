"""Проведение документов: применение и обратное применение к остаткам.

Все функции вызываются ВНУТРИ открытой транзакции: если что-то пошло
не так (например, отрицательный остаток) — откат целиком.
"""
from sqlalchemy.orm import Session

from .core import StockError, allow_negative_stock
from .models import (
    DOC_IN, DOC_INVENTORY, DOC_OUT, DOC_TRANSFER, DOC_WRITEOFF,
    Document, Item, Stock, Warehouse,
)


def _apply_line(db: Session, item_id: int, warehouse_id: int, delta: float, touched: dict) -> None:
    """Добавить delta к остатку (может быть отрицательным).

    touched — dict (item_id, warehouse_id) → Stock: объект ведётся прямо,
    т.к. Session.get с составным ключом не видит ещё не прощёнанные записи.
    """
    key = (item_id, warehouse_id)
    s = touched.get(key)
    if s is None:
        s = db.get(Stock, key)
        if s is None:
            s = Stock(item_id=item_id, warehouse_id=warehouse_id)
            db.add(s)
        touched[key] = s
    # float(): qty из БД приходит Decimal (Numeric), а строки документов — float.
    # (В длинных сессиях объект из identity map может быть перезагружен из БД.)
    s.qty = float(s.qty or 0) + float(delta)


def _check_negative(db: Session, touched: dict) -> None:
    """Контроль отрицательных остатков (настраивается: Админ → Настройки)."""
    if allow_negative_stock(db):
        return
    for s in touched.values():
        if s.qty is not None and s.qty < 0:
            item = db.get(Item, s.item_id)
            wh = db.get(Warehouse, s.warehouse_id)
            raise StockError(
                "INSUFFICIENT_STOCK",
                f"Недостаточно остатка: «{item.name}» (склад «{wh.name}»): {s.qty:g}. "
                "Уменьшите количество или включите «отрицательные остатки» в настройках.",
            )


def apply_doc(db: Session, doc: Document) -> None:
    """Применить документ к остаткам (приход +, расход −, перемещение −/+, инвентаризация по разнице)."""
    touched: dict = {}
    if doc.type == DOC_IN:
        for li in doc.items:
            if not li.warehouse_to_id:
                raise StockError("BAD_LINE", f"Строка «{li.item.name}»: не указан склад получения")
            _apply_line(db, li.item_id, li.warehouse_to_id, +li.qty, touched)
    elif doc.type in (DOC_OUT, DOC_WRITEOFF):
        for li in doc.items:
            if not li.warehouse_from_id:
                raise StockError("BAD_LINE", f"Строка «{li.item.name}»: не указан склад списания")
            _apply_line(db, li.item_id, li.warehouse_from_id, -li.qty, touched)
    elif doc.type == DOC_TRANSFER:
        for li in doc.items:
            if not li.warehouse_from_id or not li.warehouse_to_id:
                raise StockError("BAD_LINE", f"Строка «{li.item.name}»: не указаны склады «откуда» и «куда»")
            if li.warehouse_from_id == li.warehouse_to_id:
                raise StockError("BAD_LINE", f"Строка «{li.item.name}»: склады «откуда» и «куда» совпадают")
            _apply_line(db, li.item_id, li.warehouse_from_id, -li.qty, touched)
            _apply_line(db, li.item_id, li.warehouse_to_id, +li.qty, touched)
    elif doc.type == DOC_INVENTORY:
        if not doc.warehouse_id:
            raise StockError("BAD_LINE", "Для инвентаризации не указан склад")
        for r in doc.inventory_results:
            if r.diff_qty:
                _apply_line(db, r.item_id, doc.warehouse_id, r.diff_qty, touched)
    else:
        raise StockError("BAD_DOC", f"Неизвестный тип документа: {doc.type}")
    _check_negative(db, touched)


def reverse_doc(db: Session, doc: Document) -> None:
    """Обратное применение (отмена проведённого документа)."""
    touched: dict = {}
    if doc.type == DOC_IN:
        for li in doc.items:
            _apply_line(db, li.item_id, li.warehouse_to_id, -li.qty, touched)
    elif doc.type in (DOC_OUT, DOC_WRITEOFF):
        for li in doc.items:
            _apply_line(db, li.item_id, li.warehouse_from_id, +li.qty, touched)
    elif doc.type == DOC_TRANSFER:
        for li in doc.items:
            _apply_line(db, li.item_id, li.warehouse_from_id, +li.qty, touched)
            _apply_line(db, li.item_id, li.warehouse_to_id, -li.qty, touched)
    elif doc.type == DOC_INVENTORY:
        for r in doc.inventory_results:
            if r.diff_qty:
                _apply_line(db, r.item_id, doc.warehouse_id, -r.diff_qty, touched)
    _check_negative(db, touched)


def fill_inventory_diffs(db: Session, doc: Document) -> None:
    """Инвентаризация: разница = фактически − остаток в книге (до проведения)."""
    for r in doc.inventory_results:
        book = db.get(Stock, (r.item_id, doc.warehouse_id))
        book_qty = book.qty if book else 0
        r.diff_qty = (r.counted_qty or 0) - (book_qty or 0)
