"""Тесты документов и остатков (Фаза 3): проведение, контроль отрицательных, отмена, инвентаризация."""
from app.db import SessionLocal
from app.models import Setting


# ---------- Помощники ----------
def _unit_id(client, auth, name="шт"):
    return next(u["id"] for u in client.get("/api/units", headers=auth).json() if u["name"] == name)


def _warehouse_id(client, auth):
    return client.get("/api/warehouses", headers=auth).json()[0]["id"]


def _make_item(client, auth, name, sku):
    r = client.post("/api/items", json={"name": name, "sku": sku, "unit_id": _unit_id(client, auth)}, headers=auth)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _create_and_post(client, auth, doc_type, items, **header):
    payload = {"type": doc_type, "date": "2026-08-21", "items": items, **header}
    r = client.post("/api/documents", json=payload, headers=auth)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["status"] == "draft" and doc["number"] is None  # номер назначается при проведении
    r = client.post(f"/api/documents/{doc['id']}/post", headers=auth)
    assert r.status_code == 200, r.text
    return r.json()


def _stock_qty(client, auth, item_id, warehouse_id=None):
    wh = warehouse_id or _warehouse_id(client, auth)
    rows = client.get("/api/stock", headers=auth).json()["rows"]
    match = [r for r in rows if r["item_id"] == item_id and r["warehouse_id"] == wh]
    return match[0]["qty"] if match else 0


# ---------- Тесты ----------
def test_in_post_increases_stock(client, auth):
    it = _make_item(client, auth, "Товар-приход", "IN-1")
    wh = _warehouse_id(client, auth)
    doc = _create_and_post(client, auth, "in", [{"item_id": it, "warehouse_to_id": wh, "qty": 100, "price": 10}])
    assert doc["status"] == "posted"
    assert doc["number"].startswith("ПРИХ-2026-")
    assert _stock_qty(client, auth, it) == 100


def test_out_post_decreases_stock(client, auth):
    it = _make_item(client, auth, "Товар-расход", "OUT-1")
    wh = _warehouse_id(client, auth)
    _create_and_post(client, auth, "in", [{"item_id": it, "warehouse_to_id": wh, "qty": 100}])
    _create_and_post(client, auth, "out", [{"item_id": it, "warehouse_from_id": wh, "qty": 30}])
    assert _stock_qty(client, auth, it) == 70


def test_out_negative_blocked(client, auth):
    """Контроль отрицательных остатков: по умолчанию включён."""
    it = _make_item(client, auth, "Товар-нехватка", "LACK-1")
    wh = _warehouse_id(client, auth)
    doc_r = client.post("/api/documents", json={
        "type": "out", "date": "2026-08-21",
        "items": [{"item_id": it, "warehouse_from_id": wh, "qty": 150}],
    }, headers=auth)
    doc = doc_r.json()
    r = client.post(f"/api/documents/{doc['id']}/post", headers=auth)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "INSUFFICIENT_STOCK"
    assert _stock_qty(client, auth, it) == 0  # откат: остаток не тронут


def test_negative_allowed_by_setting(client, auth):
    """После включения «отрицательные остатки» расход сверх остатка проходит."""
    it = _make_item(client, auth, "Товар-отриц", "NEG-1")
    wh = _warehouse_id(client, auth)
    db = SessionLocal()
    db.get(Setting, "allow_negative_stock").value = "true"
    db.commit()
    db.close()
    try:
        _create_and_post(client, auth, "out", [{"item_id": it, "warehouse_from_id": wh, "qty": 50}])
        assert _stock_qty(client, auth, it) == -50
    finally:
        db = SessionLocal()
        db.get(Setting, "allow_negative_stock").value = "false"
        db.commit()
        db.close()


def test_transfer_moves_between_warehouses(client, auth):
    wh1 = _warehouse_id(client, auth)
    r = client.post("/api/warehouses", json={"name": "Склад-2", "active": True}, headers=auth)
    assert r.status_code == 200, r.text
    wh2 = r.json()["id"]
    it = _make_item(client, auth, "Товар-перем", "TR-1")
    _create_and_post(client, auth, "in", [{"item_id": it, "warehouse_to_id": wh1, "qty": 50}])
    doc = _create_and_post(client, auth, "transfer", [
        {"item_id": it, "warehouse_from_id": wh1, "warehouse_to_id": wh2, "qty": 20}])
    assert doc["number"].startswith("ПЕРЕМ-2026-")
    assert _stock_qty(client, auth, it, wh1) == 30
    assert _stock_qty(client, auth, it, wh2) == 20


def test_transfer_same_warehouse_rejected(client, auth):
    wh = _warehouse_id(client, auth)
    it = _make_item(client, auth, "Товар-перем2", "TR-2")
    doc_r = client.post("/api/documents", json={
        "type": "transfer", "date": "2026-08-21",
        "items": [{"item_id": it, "warehouse_from_id": wh, "warehouse_to_id": wh, "qty": 5}],
    }, headers=auth)
    r = client.post(f"/api/documents/{doc_r.json()['id']}/post", headers=auth)
    assert r.status_code == 409  # склады совпадают


def test_inventory_corrects_stock(client, auth):
    it = _make_item(client, auth, "Товар-инв", "INV-1")
    wh = _warehouse_id(client, auth)
    _create_and_post(client, auth, "in", [{"item_id": it, "warehouse_to_id": wh, "qty": 50}])
    r = client.post("/api/documents", json={
        "type": "inventory", "date": "2026-08-21", "warehouse_id": wh,
        "results": [{"item_id": it, "counted_qty": 45}],
    }, headers=auth)
    assert r.status_code == 200, r.text
    doc = client.post(f"/api/documents/{r.json()['id']}/post", headers=auth).json()
    assert doc["number"].startswith("ИНВ-2026-")
    assert doc["results"][0]["diff_qty"] == -5
    assert _stock_qty(client, auth, it) == 45


def test_cancel_reverses_stock(client, auth):
    it = _make_item(client, auth, "Товар-отмена", "CXL-1")
    wh = _warehouse_id(client, auth)
    doc = _create_and_post(client, auth, "in", [{"item_id": it, "warehouse_to_id": wh, "qty": 100}])
    assert _stock_qty(client, auth, it) == 100
    r = client.post(f"/api/documents/{doc['id']}/cancel", headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert _stock_qty(client, auth, it) == 0
    # Повторное проведение отменённого — нельзя
    assert client.post(f"/api/documents/{doc['id']}/post", headers=auth).status_code == 409
    # Повторная отмена — тоже нельзя
    assert client.post(f"/api/documents/{doc['id']}/cancel", headers=auth).status_code == 409


def test_draft_does_not_touch_stock(client, auth):
    it = _make_item(client, auth, "Товар-черновик", "DFT-1")
    wh = _warehouse_id(client, auth)
    r = client.post("/api/documents", json={
        "type": "in", "date": "2026-08-21",
        "items": [{"item_id": it, "warehouse_to_id": wh, "qty": 999}],
    }, headers=auth)
    assert r.status_code == 200
    assert _stock_qty(client, auth, it) == 0


def test_number_sequential_per_year(client, auth):
    it = _make_item(client, auth, "Товар-нумер", "NUM-1")
    wh = _warehouse_id(client, auth)
    d1 = _create_and_post(client, auth, "in", [{"item_id": it, "warehouse_to_id": wh, "qty": 1}])
    d2 = _create_and_post(client, auth, "in", [{"item_id": it, "warehouse_to_id": wh, "qty": 1}])
    n1, n2 = int(d1["number"].rsplit("-", 1)[1]), int(d2["number"].rsplit("-", 1)[1])
    assert n2 == n1 + 1


def test_create_validation(client, auth):
    wh = _warehouse_id(client, auth)
    # Без строк — 400
    r = client.post("/api/documents", json={"type": "in", "date": "2026-08-21", "items": []}, headers=auth)
    assert r.status_code == 400
    # Несуществующий товар — 400
    r = client.post("/api/documents", json={
        "type": "in", "date": "2026-08-21",
        "items": [{"item_id": 99999, "warehouse_to_id": wh, "qty": 1}],
    }, headers=auth)
    assert r.status_code == 400
    # Инвентаризация без склада — 400
    it = _make_item(client, auth, "Товар-инв2", "INV-2")
    r = client.post("/api/documents", json={
        "type": "inventory", "date": "2026-08-21", "warehouse_id": None,
        "results": [{"item_id": it, "counted_qty": 1}],
    }, headers=auth)
    assert r.status_code == 400


def test_list_documents_filter(client, auth):
    wh = _warehouse_id(client, auth)
    r = client.get("/api/documents", params={"type": "in"}, headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert all(d["type"] == "in" for d in body["documents"])
    # Поиск по номеру
    num = body["documents"][0]["number"]
    r = client.get("/api/documents", params={"q": num}, headers=auth)
    assert any(d["number"] == num for d in r.json()["documents"])
