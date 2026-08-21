"""Ядро: исключения, аудит, нумерация документов."""
import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import AuditLog, DocNumber, Setting
from .models.documents import DOC_NUMBER_PREFIX


class StockError(HTTPException):
    """Ошибка операции со складами (недостаточно остатка и т.п.).

    code передаётся в UI для локализации сообщения:
    - INSUFFICIENT_STOCK — не хватает остатка (контроль отрицательных включён)
    """

    def __init__(self, code: str, message: str):
        super().__init__(status_code=409, detail={"code": code, "message": message})
        self.code = code


def audit(
    db: Session,
    user_id: int | None,
    action: str,
    entity: str,
    entity_id: int | str | None = None,
    changes: dict | None = None,
) -> None:
    """Запись в журнал аудита (вызывается внутри той же транзакции операции)."""
    db.add(
        AuditLog(
            ts=datetime.utcnow(),
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            changes=json.dumps(changes, ensure_ascii=False) if changes else None,
        )
    )


def next_document_number(db: Session, doc_type: str, year: int) -> str:
    """Следующий номер документа вида ПРИХ-2026-0001 (счётчик в таблице doc_numbers)."""
    counter = db.get(DocNumber, (doc_type, year))
    if counter is None:
        counter = DocNumber(type=doc_type, year=year, last_number=0)
        db.add(counter)
        db.flush()
    counter.last_number += 1
    prefix = DOC_NUMBER_PREFIX[doc_type]
    return f"{prefix}-{year}-{counter.last_number:04d}"


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.get(Setting, key)
    return row.value if row else default


def allow_negative_stock(db: Session) -> bool:
    return get_setting(db, "allow_negative_stock", "false") == "true"


def default_warehouse_id(db: Session) -> int | None:
    value = get_setting(db, "default_warehouse_id", "")
    return int(value) if value else None
