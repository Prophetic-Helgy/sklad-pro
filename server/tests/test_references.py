"""Тесты CRUD справочников (Фаза 2): ед. изм., категории, товары, контрагенты, склады."""
from app.db import SessionLocal
from app.models import Item, Stock


# ---------- Единицы измерения ----------
def test_units_crud(client, auth):
    r = client.post("/api/units", json={"name": "уп."}, headers=auth)
    assert r.status_code == 200, r.text
    uid = r.json()["id"]
    # Дубликат — 409
    assert client.post("/api/units", json={"name": "уп."}, headers=auth).status_code == 409
    # Изменение
    r = client.put(f"/api/units/{uid}", json={"name": "упак."}, headers=auth)
    assert r.status_code == 200 and r.json()["name"] == "упак."


def test_unit_delete_refused_when_used(client, auth):
    r = client.post("/api/units", json={"name": "короткая-ед"}, headers=auth)
    uid = r.json()["id"]
    # Привязываем к товару
    item = client.post("/api/items", json={
        "name": "Товар-для-ед", "sku": "T-FOR-UNIT", "unit_id": uid,
    }, headers=auth)
    assert item.status_code == 200, item.text
    assert client.delete(f"/api/units/{uid}", headers=auth).status_code == 409
    # Удалили товар — можно удалить ед. изм.
    client.delete(f"/api/items/{item.json()['id']}", headers=auth)
    assert client.delete(f"/api/units/{uid}", headers=auth).status_code == 204


# ---------- Категории ----------
def test_categories_tree_and_protection(client, auth):
    p = client.post("/api/categories", json={"name": "Крепёж", "parent_id": None}, headers=auth)
    assert p.status_code == 200, p.text
    c = client.post("/api/categories", json={"name": "Болты", "parent_id": p.json()["id"]}, headers=auth)
    assert c.status_code == 200
    # Пустую категорию можно удалить
    d = client.post("/api/categories", json={"name": "Пусто", "parent_id": None}, headers=auth)
    assert client.delete(f"/api/categories/{d.json()['id']}", headers=auth).status_code == 204
    # Категорию с товаром удалить нельзя
    units = client.get("/api/units", headers=auth).json()
    item = client.post("/api/items", json={
        "name": "Товар-в-категории", "sku": "T-IN-CAT",
        "unit_id": units[0]["id"], "category_id": c.json()["id"],
    }, headers=auth)
    assert item.status_code == 200
    assert client.delete(f"/api/categories/{c.json()['id']}", headers=auth).status_code == 409


# ---------- Товары (Номенклатура) ----------
def _make_item(client, auth, name="Товар А", sku="SKU-A", barcode="111", unit_name="шт"):
    units = client.get("/api/units", headers=auth).json()
    uid = next(u["id"] for u in units if u["name"] == unit_name)
    r = client.post("/api/items", json={"name": name, "sku": sku, "barcode": barcode, "unit_id": uid}, headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


def test_item_create_and_uniques(client, auth):
    it = _make_item(client, auth)
    assert it["unit_name"] == "шт"
    # Уникальность по наименованию / артикулу / штрих-коду
    units = client.get("/api/units", headers=auth).json()[0]
    assert client.post("/api/items", json={"name": "Товар А", "sku": "X1", "unit_id": units["id"]}, headers=auth).status_code == 409
    assert client.post("/api/items", json={"name": "Б", "sku": "SKU-A", "unit_id": units["id"]}, headers=auth).status_code == 409
    assert client.post("/api/items", json={"name": "В", "sku": "X2", "barcode": "111", "unit_id": units["id"]}, headers=auth).status_code == 409


def test_item_search_and_deactivate(client, auth):
    it = _make_item(client, auth, name="Гайка М10", sku="GAYKA-10", barcode="222")
    # Поиск по части наименования
    r = client.get("/api/items", params={"q": "гайка"}, headers=auth)
    assert any(i["id"] == it["id"] for i in r.json()["items"])
    # Поиск по артикулу (префикс) и штрих-коду
    assert any(i["id"] == it["id"] for i in client.get("/api/items", params={"q": "GAYKA"}, headers=auth).json()["items"])
    assert any(i["id"] == it["id"] for i in client.get("/api/items", params={"q": "222"}, headers=auth).json()["items"])
    # Не существует
    assert client.get("/api/items", params={"q": "нет-такого"}, headers=auth).json()["total"] == 0
    # Деактивация: скрывается из общего списка, видна с include_inactive
    r = client.post(f"/api/items/{it['id']}/deactivate", headers=auth)
    assert r.status_code == 200 and r.json()["active"] is False
    assert all(i["id"] != it["id"] for i in client.get("/api/items", headers=auth).json()["items"])
    assert any(i["id"] == it["id"] for i in client.get("/api/items", params={"include_inactive": "true"}, headers=auth).json()["items"])


def test_item_update(client, auth):
    it = _make_item(client, auth, name="Обновляемый", sku="UPD-1", barcode=None)
    r = client.put(f"/api/items/{it['id']}", json={
        "name": "Обновлённый", "sku": "UPD-1", "unit_id": it["unit_id"], "sale_price": 100,
    }, headers=auth)
    assert r.status_code == 200
    assert r.json()["name"] == "Обновлённый"
    assert float(r.json()["sale_price"]) == 100


def test_item_brief_for_documents(client, auth):
    _make_item(client, auth, name="Для-брифа", sku="BRIEF-1", barcode=None)
    r = client.get("/api/items/brief", params={"q": "бриф"}, headers=auth)
    assert r.status_code == 200
    assert any(i["sku"] == "BRIEF-1" for i in r.json())


# ---------- Контрагенты ----------
def test_partners_crud(client, auth):
    r = client.post("/api/partners", json={
        "kind": "supplier", "full_name": 'ООО «Винт и Болт»', "inn": "7700000001", "phone": "+7 000 000-00-01",
    }, headers=auth)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    # Дубликат по наименованию
    assert client.post("/api/partners", json={"kind": "supplier", "full_name": 'ООО «Винт и Болт»'}, headers=auth).status_code == 409
    # Поиск по ИНН
    assert any(p["id"] == pid for p in client.get("/api/partners", params={"q": "7700000001"}, headers=auth).json())
    # Изменение
    r = client.put(f"/api/partners/{pid}", json={
        "kind": "both", "full_name": 'ООО «Винт и Болт»', "email": "sales@example.ru",
    }, headers=auth)
    assert r.status_code == 200 and r.json()["kind"] == "both" and r.json()["email"] == "sales@example.ru"
    # Фильтр по типу: both подходит и для supplier
    assert any(p["id"] == pid for p in client.get("/api/partners", params={"kind": "supplier"}, headers=auth).json())


def test_partner_delete_refused_when_used_in_documents(client, auth):
    """Контрагент, упомянутый в документе, не удаляется (409)."""
    from datetime import date
    from app.db import SessionLocal
    from app.models import Document, User
    partner = client.post("/api/partners", json={"kind": "supplier", "full_name": "Поставщик-не-удалить"}, headers=auth)
    pid = partner.json()["id"]
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username="admin").first()
        doc = Document(type="in", number="ТЕСТ-1", date=date.today(), status="draft",
                       partner_id=pid, created_by=user.id)
        db.add(doc)
        db.commit()
        assert client.delete(f"/api/partners/{pid}", headers=auth).status_code == 409
        # Чистим тестовый документ
        db.query(Document).filter_by(number="ТЕСТ-1").delete()
        db.commit()
        assert client.delete(f"/api/partners/{pid}", headers=auth).status_code == 204
    finally:
        db.close()


# ---------- Склады ----------
def test_warehouses_crud_and_protection(client, auth):
    r = client.post("/api/warehouses", json={"name": "Приёмка", "active": True}, headers=auth)
    assert r.status_code == 200, r.text
    wid = r.json()["id"]
    # Дубликат
    assert client.post("/api/warehouses", json={"name": "Приёмка", "active": True}, headers=auth).status_code == 409
    # Склад с остатком удалить нельзя
    db = SessionLocal()
    try:
        item = db.query(Item).first()
        db.add(Stock(item_id=item.id, warehouse_id=wid, qty=5))
        db.commit()
    finally:
        db.close()
    assert client.delete(f"/api/warehouses/{wid}", headers=auth).status_code == 409
    # Изменение
    r = client.put(f"/api/warehouses/{wid}", json={"name": "Приёмка-2", "active": False}, headers=auth)
    assert r.status_code == 200 and r.json()["active"] is False
