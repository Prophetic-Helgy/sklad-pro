"""Авторизация: вход, текущий пользователь, список сотрудников."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.users import User, AuditLog
from ..schemas.auth import LoginIn, TokenOut, UserOut
from ..security import create_token, get_current_admin, get_current_user, verify_password
from .. import config

router = APIRouter(prefix="/auth", tags=["Авторизация"])


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    if not user.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Учётная запись заблокирована")
    db.add(AuditLog(user_id=user.id, action="login", entity="auth", entity_id=str(user.id)))
    db.commit()
    return TokenOut(access_token=create_token(user))


@router.post("/logout")
def logout(user: User = Depends(get_current_user)):
    # JWT безсессионный: достаточно удалить токен на клиенте
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Список сотрудников (для поля «Отпустил» и справочных списков)."""
    return db.scalars(select(User).where(User.active == True).order_by(User.username)).all()  # noqa: E712


@router.get("/info")
def info():
    """Служебная информация (версия, имя приложения) — без авторизации."""
    return {"name": config.APP_NAME, "version": config.APP_VERSION}
