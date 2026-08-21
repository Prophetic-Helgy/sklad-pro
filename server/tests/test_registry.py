"""Тесты реестров (Фаза 4): построчный журнал, фильтры, исключение черновиков и отменённых.

База общая для всех тестов (session-scoped), поэтому каждый тест
пользуется собственной датой документов и уникальными артикулами.
"""
from tests.test_documents import _create_and_post, _make_item, _warehouse_id


def test_registry_shows_posted_lines(client, auth):
    it = _make_item(client, auth, "Товар-реестр-1", "REG-1")
    wh = _warehouse_id(client, auth)
    doc = _create_and_post(client, auth, "in", [
        {"item_id": it, "warehouse_to_id": wh, "qty": 100, "price": 10},
    ], doc_ref="НК-77", date="2026-07-01")
    r = client.get("/api/registry/in?date_from=2026-07-01&date_to=2026-07-01", headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    row = body["rows"][0]
    assert row["doc_number"] == doc["number"]
    assert row["item_name"] == "Товар-реестр-1"
    assert row["sku"] == "REG-1"
    assert row["qty"] == 100
    assert row["doc_ref"] == "НК-77"


def test_registry_excludes_drafts_and_cancelled(client, auth):
    it = _make_item(client, auth, "Товар-реестр-2", "REG-2")
    wh = _warehouse_id(client, auth)
    d = "2026-07-02"
    doc = _create_and_post(client, auth, "in", [{"item_id": it, "warehouse_to_id": wh, "qty": 10}], date=d)
    # Черновик не попадает в реестр
    client.post("/api/documents", json={
        "type": "in", "date": d,
        "items": [{"item_id": it, "warehouse_to_id": wh, "qty": 5}],
    }, headers=auth)
    count = lambda: client.get(f"/api/registry/in?date_from={d}&date_to={d}", headers=auth).json()["total"]
    assert count() == 1
    # Отмена — строка исчезает
    client.post(f"/api/documents/{doc['id']}/cancel", headers=auth)
    assert count() == 0


def test_registry_filters(client, auth):
    it = _make_item(client, auth, "Товар-реестр-3", "REG-3")
    wh = _warehouse_id(client, auth)
    d = "2026-07-03"
    p1 = client.post("/api/partners", json={"kind": "supplier", "full_name": "П-Рег-1"}, headers=auth).json()
    p2 = client.post("/api/partners", json={"kind": "supplier", "full_name": "П-Рег-2"}, headers=auth).json()
    _create_and_post(client, auth, "in", [{"item_id": it, "warehouse_to_id": wh, "qty": 100}], partner_id=p1["id"], date=d)
    _create_and_post(client, auth, "in", [{"item_id": it, "warehouse_to_id": wh, "qty": 50}], partner_id=p2["id"], date=d)

    base = "/api/registry/in"
    assert client.get(f"{base}?date_from={d}&date_to={d}", headers=auth).json()["total"] == 2
    # По контрагенту
    r = client.get(f"{base}?partner_id={p1['id']}", headers=auth).json()
    assert r["total"] == 1 and r["rows"][0]["qty"] == 100
    # Поиск по артикулу (уникальный)
    assert client.get(f"{base}?q=REG-3", headers=auth).json()["total"] == 2
    assert client.get(f"{base}?q=нет-такого", headers=auth).json()["total"] == 0
    # Пустой период (в общей БД могут быть документы других дат)
    assert client.get(f"{base}?date_from=2026-06-01&date_to=2026-06-30", headers=auth).json()["total"] == 0


def test_registry_out_fields(client, auth):
    it = _make_item(client, auth, "Товар-реестр-4", "REG-4")
    wh = _warehouse_id(client, auth)
    d = "2026-07-04"
    me = client.get("/api/auth/me", headers=auth).json()
    # Сначала приход, чтобы на расход был остаток
    _create_and_post(client, auth, "in", [{"item_id": it, "warehouse_to_id": wh, "qty": 50}], date="2026-07-03")
    doc = _create_and_post(client, auth, "out", [{"item_id": it, "warehouse_from_id": wh, "qty": 10}],
                           received_by="Иванов И.И.", out_by_id=me["id"], date=d)
    r = client.get(f"/api/registry/out?date_from={d}&date_to={d}", headers=auth).json()
    assert r["total"] == 1
    row = r["rows"][0]
    assert row["doc_number"] == doc["number"]
    assert row["received_by"] == "Иванов И.И."
    assert row["out_by_name"] == me["full_name"]
