"""Раздел «Админ»: карточка предприятия, пользователи, настройки, аудит, бэкап/восстановление."""
import os
import shutil
import sqlite3
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from ..config import BACKUP_DIR, DB_PATH
from ..core import audit
from ..db import SessionLocal, engine, get_db
from ..models import AuditLog, Company, Setting, User
from ..schemas.admin import (
    AuditPageOut,
    AuditRowOut,
    CompanyIn,
    SettingOut,
    SettingUpdate,
    UserIn,
    UserOut,
    UserUpdate,
)
from ..schemas.references import CompanyOut
from ..security import get_current_admin, hash_password

router = APIRouter(tags=["Админ"])

# Настройки, доступные к изменению из раздела «Админ»
_SETTING_DEFAULTS = {
    "allow_negative_stock": "false",
    "default_warehouse_id": "",
}


@router.put("/company", response_model=CompanyOut)
def update_company(
    payload: CompanyIn,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Обновление карточки предприятия (строка с id=1)."""
    comp = db.get(Company, 1)
    if comp is None:
        comp = Company(id=1)
        db.add(comp)
    changes: dict = {}
    for field, value in payload.model_dump(exclude_unset=True).items():
        old = getattr(comp, field)
        if old != value:
            changes[field] = {"old": old, "new": value}
        setattr(comp, field, value)
    if changes:
        audit(db, admin.id, "update", "company", 1, changes)
    db.commit()
    db.refresh(comp)
    return comp


@router.get("/admin/users", response_model=list[UserOut])
def list_users(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.post("/admin/users", response_model=UserOut, status_code=201)
def create_user(
    payload: UserIn,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if db.scalar(select(User).where(func.ci_lower(User.username) == payload.username.lower())):
        raise HTTPException(status_code=409, detail="Пользователь с таким логином уже существует")
    new_user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        active=True,
    )
    db.add(new_user)
    audit(db, admin.id, "create", "users", payload.username, {"role": payload.role})
    db.commit()
    db.refresh(new_user)
    return new_user


@router.put("/admin/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    data = payload.model_dump(exclude_unset=True)
    # Защита от самоблокировки: нельзя лишить себя роли или заблокировать
    if admin.id == user_id:
        if data.get("role") is not None and data["role"] != "admin":
            raise HTTPException(status_code=400, detail="Нельзя изменить собственную роль администратора")
        if data.get("active") is not None and not data["active"]:
            raise HTTPException(status_code=400, detail="Нельзя заблокировать себя")
    changes: dict = {}
    for field in ("full_name", "role", "active"):
        if data.get(field) is not None and getattr(target, field) != data[field]:
            changes[field] = {"old": getattr(target, field), "new": data[field]}
            setattr(target, field, data[field])
    if data.get("password"):
        target.password_hash = hash_password(data["password"])
        changes["password"] = "***"
    if changes:
        audit(db, admin.id, "update", "users", target.username, changes)
    db.commit()
    db.refresh(target)
    return target


@router.get("/admin/settings", response_model=list[SettingOut])
def list_settings(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    rows = {r.key: r.value for r in db.scalars(select(Setting)).all()}
    return [SettingOut(key=k, value=rows.get(k, _SETTING_DEFAULTS[k])) for k in _SETTING_DEFAULTS]


@router.put("/admin/settings", response_model=SettingOut)
def update_setting(
    payload: SettingUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if payload.key not in _SETTING_DEFAULTS:
        raise HTTPException(status_code=400, detail=f"Неизвестная настройка: {payload.key}")
    row = db.get(Setting, payload.key)
    old = row.value if row else _SETTING_DEFAULTS[payload.key]
    if row is None:
        row = Setting(key=payload.key)
        db.add(row)
    row.value = payload.value
    audit(db, admin.id, "update", "settings", payload.key, {"old": old, "new": payload.value})
    db.commit()
    return SettingOut(key=payload.key, value=payload.value)


@router.get("/admin/audit", response_model=AuditPageOut)
def audit_list(
    user_id: int | None = None,
    action: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Журнал изменений с фильтрами и постраничной выдачей."""
    stmt = select(AuditLog, User.username).outerjoin(User, AuditLog.user_id == User.id)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if date_from:
        stmt = stmt.where(AuditLog.ts >= datetime.combine(date_from, time.min))
    if date_to:
        stmt = stmt.where(AuditLog.ts < datetime.combine(date_to + timedelta(days=1), time.min))
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.ci_lower(AuditLog.action).like(like),
                func.ci_lower(AuditLog.entity).like(like),
                func.ci_lower(User.username).like(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(AuditLog.ts.desc(), AuditLog.id.desc()).offset((page - 1) * size).limit(size)
    ).all()
    return AuditPageOut(
        total=total,
        rows=[
            AuditRowOut(
                id=log.id,
                ts=log.ts,
                user_id=log.user_id,
                username=username,
                action=log.action,
                entity=log.entity,
                entity_id=log.entity_id,
                changes=log.changes,
            )
            for log, username in rows
        ],
    )


@router.get("/admin/backup")
def backup(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Скачать резервную копию базы (SQLite-файл)."""
    db.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = BACKUP_DIR / f"склад_{stamp}.db"
    shutil.copy2(DB_PATH, path)
    audit(db, admin.id, "backup", "backup", None, {"file": path.name})
    db.commit()
    return FileResponse(path, filename=f"склад_{stamp}.db", media_type="application/octet-stream")


@router.post("/admin/restore")
async def restore(
    file: UploadFile = File(...),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Восстановить базу из файла .db (проверка целостности + снимок текущей базы)."""
    data = await file.read()
    if len(data) < 100 or not data.startswith(b"SQLite format 3\x00"):
        raise HTTPException(status_code=400, detail="Файл не является базой SQLite")
    tmp = BACKUP_DIR / f"_restore_tmp_{os.getpid()}.db"
    tmp.write_bytes(data)
    try:
        conn = sqlite3.connect(str(tmp))
        try:
            ok = conn.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            conn.close()
        if ok != "ok":
            raise HTTPException(status_code=400, detail=f"Файл восстановления не прошёл проверку целостности: {ok}")
    except HTTPException:
        tmp.unlink(missing_ok=True)
        raise
    # Снимок текущей базы до замены — можно откатиться назад
    db.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    snap = BACKUP_DIR / f"склад_снимок_до_восстановления_{stamp}.db"
    shutil.copy2(DB_PATH, snap)
    audit(db, admin.id, "restore", "backup", None, {"file": file.filename, "snapshot": snap.name})
    db.commit()
    # Закрываем все открытые соединения, чтобы файл можно было заменить
    db.close()
    engine.dispose()
    os.replace(tmp, DB_PATH)
    # Запись в журнал уже новой базы (id пользователя из старой базы может не существовать)
    with SessionLocal() as new_db:
        audit(new_db, None, "restore", "backup", None, {"file": file.filename, "user": admin.username, "result": "ok"})
        new_db.commit()
    return {"ok": True, "snapshot": snap.name}
