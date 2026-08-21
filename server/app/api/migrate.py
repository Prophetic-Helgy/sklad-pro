"""Миграция: импорт файла «Склад ПРО 7.1» и экспорт данных в его формат."""
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import migrate_xlsm
from ..db import get_db
from ..security import get_current_admin, User

router = APIRouter(tags=["Миграция"])


@router.post("/admin/migrate/import")
async def migrate_import(
    file: UploadFile = File(...),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Перенести данные из файла 7.1 (.xlsm/.xlsx). Возвращает отчёт о переносе."""
    data = await file.read()
    if not data.startswith(b"PK"):
        raise HTTPException(status_code=400, detail="Файл не является Excel (.xlsm/.xlsx)")
    try:
        return migrate_xlsm.import_xlsm(db, data, user_id=admin.id)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Импорт не выполнен: {e}") from e


@router.get("/admin/migrate/export")
def migrate_export(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Экспортировать текущие данные в файл с структурой листов 7.1."""
    content, name = migrate_xlsm.export_71(db)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"},
    )
