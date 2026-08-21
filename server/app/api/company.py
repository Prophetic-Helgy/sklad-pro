"""Карточка предприятия: чтение — для печатных форм; редактирование — раздел «Админ»."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Company, User
from ..schemas.references import CompanyOut
from ..security import get_current_user

router = APIRouter(tags=["Предприятие"])


@router.get("/company", response_model=CompanyOut | None)
def get_company(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalar(select(Company).where(Company.id == 1))
