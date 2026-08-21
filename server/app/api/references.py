"""CRUD справочников: товары, ед. изм, категории, контрагенты, склады.

Удаление: если запись используется в остатках/документах — запрещаем
жёсткое удаление (409), вместо этого деактивация (active=false).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import core
from ..db import get_db
from ..models import Category, Document, DocumentItem, Item, Partner, Stock, Unit, User, Warehouse
from ..schemas.references import (
    CategoryIn, CategoryOut, ItemIn, ItemOut, PartnerIn, PartnerOut,
    UnitIn, UnitOut, WarehouseIn, WarehouseOut, PageOut,
)
from ..security import get_current_user

router = APIRouter(tags=["Справочники"])


def _refused_deletion():
    raise HTTPException(status_code=409, detail="Запись используется в остатках или документах — выполните деактивацию")


# ================= Единицы измерения =================
@router.get("/units", response_model=list[UnitOut])
def list_units(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(Unit).order_by(Unit.name)).all()


@router.post("/units", response_model=UnitOut)
def create_unit(data: UnitIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.scalar(select(Unit).where(Unit.name == data.name)):
        raise HTTPException(409, f"Ед. изм. «{data.name}» уже существует")
    unit = Unit(**data.model_dump())
    db.add(unit)
    core.audit(db, user.id, "create", "units", unit.id, data.model_dump())
    db.commit()
    db.refresh(unit)
    return unit


@router.put("/units/{unit_id}", response_model=UnitOut)
def update_unit(unit_id: int, data: UnitIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    unit = db.get(Unit, unit_id) or _not_found("Ед. изм.")
    if db.scalar(select(Unit).where(Unit.name == data.name, Unit.id != unit_id)):
        raise HTTPException(409, f"Ед. изм. «{data.name}» уже существует")
    unit.name = data.name
    core.audit(db, user.id, "update", "units", unit.id, data.model_dump())
    db.commit()
    db.refresh(unit)
    return unit


@router.delete("/units/{unit_id}", status_code=204)
def delete_unit(unit_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    unit = db.get(Unit, unit_id) or _not_found("Ед. изм.")
    if db.scalar(select(func.count()).select_from(Item).where(Item.unit_id == unit_id)):
        _refused_deletion()
    db.delete(unit)
    core.audit(db, user.id, "delete", "units", unit_id)
    db.commit()


# ================= Категории =================
@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(Category).order_by(Category.name)).all()


@router.post("/categories", response_model=CategoryOut)
def create_category(data: CategoryIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.scalar(select(Category).where(Category.name == data.name)):
        raise HTTPException(409, f"Категория «{data.name}» уже существует")
    cat = Category(**data.model_dump())
    db.add(cat)
    core.audit(db, user.id, "create", "categories", cat.id, data.model_dump())
    db.commit()
    db.refresh(cat)
    return cat


@router.put("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, data: CategoryIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cat = db.get(Category, category_id) or _not_found("Категория")
    if db.scalar(select(Category).where(Category.name == data.name, Category.id != category_id)):
        raise HTTPException(409, f"Категория «{data.name}» уже существует")
    cat.name, cat.parent_id = data.name, data.parent_id
    core.audit(db, user.id, "update", "categories", cat.id, data.model_dump())
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cat = db.get(Category, category_id) or _not_found("Категория")
    if db.scalar(select(func.count()).select_from(Item).where(Item.category_id == category_id)):
        _refused_deletion()
    db.delete(cat)
    core.audit(db, user.id, "delete", "categories", category_id)
    db.commit()


# ================= Товары (Номенклатура) =================
@router.get("/items", response_model=PageOut)
def list_items(
    q: str | None = Query(default=None, description="Поиск: наименование (содержит), артикул/штрих-код (точное или префикс)"),
    category_id: int | None = None,
    include_inactive: bool = False,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Список товаров. Поиск повторяет поведение формы в Excel 7.1
    (поиск по началу/содержанию наименования) + точный артикул/штрих-код."""
    stmt = select(Item)
    if not include_inactive:
        stmt = stmt.where(Item.active == True)  # noqa: E712
    if category_id:
        stmt = stmt.where(Item.category_id == category_id)
    if q:
        q = q.strip()
        ql = q.lower()
        stmt = stmt.where(
            or_(
                func.ci_lower(Item.name).like(f"%{ql}%"),
                func.ci_lower(Item.sku).like(f"{ql}%"),
                Item.sku == q,
                Item.barcode == q,
                func.ci_lower(Item.barcode).like(f"{ql}%"),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(Item.name).offset((page - 1) * size).limit(size)).all()
    return PageOut(items=items, total=total or 0)


@router.get("/items/brief", response_model=list[ItemOut])
def list_items_brief(q: str | None = Query(default=None, max_length=50), limit: int = 20,
                     db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Короткий список для выпадающего выбора в документах (как ПоискНаименование в 7.1)."""
    stmt = select(Item).where(Item.active == True)  # noqa: E712
    if q:
        q = q.strip()
        ql = q.lower()
        stmt = stmt.where(or_(func.ci_lower(Item.name).like(f"{ql}%"),
                              func.ci_lower(Item.name).like(f"%{ql}%"),
                              Item.sku == q, Item.barcode == q))
    return db.scalars(stmt.order_by(Item.name).limit(limit)).all()


def _not_found(kind: str):
    raise HTTPException(404, f"{kind} не найден")


@router.post("/items", response_model=ItemOut)
def create_item(data: ItemIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.scalar(select(Item).where(Item.name == data.name)):
        raise HTTPException(409, f"Товар «{data.name}» уже существует")
    if data.sku and db.scalar(select(Item).where(Item.sku == data.sku)):
        raise HTTPException(409, f"Артикул «{data.sku}» уже занят")
    if data.barcode and db.scalar(select(Item).where(Item.barcode == data.barcode)):
        raise HTTPException(409, f"Штрих-код «{data.barcode}» уже занят")
    item = Item(**data.model_dump())
    db.add(item)
    core.audit(db, user.id, "create", "items", item.id, data.model_dump())
    db.commit()
    db.refresh(item)
    return item


@router.get("/items/{item_id}", response_model=ItemOut)
def get_item(item_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.get(Item, item_id) or _not_found("Товар")


@router.put("/items/{item_id}", response_model=ItemOut)
def update_item(item_id: int, data: ItemIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.get(Item, item_id) or _not_found("Товар")
    if db.scalar(select(Item).where(Item.name == data.name, Item.id != item_id)):
        raise HTTPException(409, f"Товар «{data.name}» уже существует")
    if data.sku and db.scalar(select(Item).where(Item.sku == data.sku, Item.id != item_id)):
        raise HTTPException(409, f"Артикул «{data.sku}» уже занят")
    if data.barcode and db.scalar(select(Item).where(Item.barcode == data.barcode, Item.id != item_id)):
        raise HTTPException(409, f"Штрих-код «{data.barcode}» уже занят")
    for field, value in data.model_dump().items():
        setattr(item, field, value)
    core.audit(db, user.id, "update", "items", item.id, data.model_dump())
    db.commit()
    db.refresh(item)
    return item


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.get(Item, item_id) or _not_found("Товар")
    if db.scalar(select(func.count()).select_from(DocumentItem).where(DocumentItem.item_id == item_id)):
        _refused_deletion()
    db.delete(item)
    core.audit(db, user.id, "delete", "items", item_id)
    db.commit()


@router.post("/items/{item_id}/deactivate", response_model=ItemOut)
def deactivate_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.get(Item, item_id) or _not_found("Товар")
    item.active = False
    core.audit(db, user.id, "update", "items", item.id, {"active": False})
    db.commit()
    db.refresh(item)
    return item


# ================= Контрагенты (Поставщики) =================
@router.get("/partners", response_model=list[PartnerOut])
def list_partners(
    q: str | None = None,
    kind: str | None = Query(default=None, pattern="^(supplier|customer|both)$"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Partner).where(Partner.active == True)  # noqa: E712
    if kind:
        # 'both' подходит и как поставщик, и как покупатель
        stmt = stmt.where((Partner.kind == kind) | (Partner.kind == "both"))
    if q:
        q = q.strip()
        stmt = stmt.where(or_(func.ci_lower(Partner.full_name).like(f"%{q.lower()}%"),
                              Partner.inn == q))
    return db.scalars(stmt.order_by(Partner.full_name)).all()


@router.post("/partners", response_model=PartnerOut)
def create_partner(data: PartnerIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.scalar(select(Partner).where(Partner.full_name == data.full_name)):
        raise HTTPException(409, f"Контрагент «{data.full_name}» уже существует")
    partner = Partner(**data.model_dump())
    db.add(partner)
    core.audit(db, user.id, "create", "partners", partner.id, data.model_dump())
    db.commit()
    db.refresh(partner)
    return partner


@router.get("/partners/{partner_id}", response_model=PartnerOut)
def get_partner(partner_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.get(Partner, partner_id) or _not_found("Контрагент")


@router.put("/partners/{partner_id}", response_model=PartnerOut)
def update_partner(partner_id: int, data: PartnerIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    partner = db.get(Partner, partner_id) or _not_found("Контрагент")
    if db.scalar(select(Partner).where(Partner.full_name == data.full_name, Partner.id != partner_id)):
        raise HTTPException(409, f"Контрагент «{data.full_name}» уже существует")
    for field, value in data.model_dump().items():
        setattr(partner, field, value)
    core.audit(db, user.id, "update", "partners", partner.id, data.model_dump())
    db.commit()
    db.refresh(partner)
    return partner


@router.delete("/partners/{partner_id}", status_code=204)
def delete_partner(partner_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    partner = db.get(Partner, partner_id) or _not_found("Контрагент")
    if db.scalar(select(func.count()).select_from(Document).where(Document.partner_id == partner_id)):
        _refused_deletion()
    db.delete(partner)
    core.audit(db, user.id, "delete", "partners", partner_id)
    db.commit()


# ================= Склады =================
@router.get("/warehouses", response_model=list[WarehouseOut])
def list_warehouses(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(Warehouse).order_by(Warehouse.name)).all()


@router.post("/warehouses", response_model=WarehouseOut)
def create_warehouse(data: WarehouseIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.scalar(select(Warehouse).where(Warehouse.name == data.name)):
        raise HTTPException(409, f"Склад «{data.name}» уже существует")
    wh = Warehouse(**data.model_dump())
    db.add(wh)
    core.audit(db, user.id, "create", "warehouses", wh.id, data.model_dump())
    db.commit()
    db.refresh(wh)
    return wh


@router.put("/warehouses/{warehouse_id}", response_model=WarehouseOut)
def update_warehouse(warehouse_id: int, data: WarehouseIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    wh = db.get(Warehouse, warehouse_id) or _not_found("Склад")
    if db.scalar(select(Warehouse).where(Warehouse.name == data.name, Warehouse.id != warehouse_id)):
        raise HTTPException(409, f"Склад «{data.name}» уже существует")
    wh.name, wh.active = data.name, data.active
    core.audit(db, user.id, "update", "warehouses", wh.id, data.model_dump())
    db.commit()
    db.refresh(wh)
    return wh


@router.delete("/warehouses/{warehouse_id}", status_code=204)
def delete_warehouse(warehouse_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    wh = db.get(Warehouse, warehouse_id) or _not_found("Склад")
    if db.scalar(select(func.count()).select_from(Stock).where(Stock.warehouse_id == warehouse_id)):
        _refused_deletion()
    db.delete(wh)
    core.audit(db, user.id, "delete", "warehouses", warehouse_id)
    db.commit()
