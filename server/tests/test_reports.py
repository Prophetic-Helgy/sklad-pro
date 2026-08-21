"""Тесты отчётов (Фаза 5): ОСВ, оборотка, движения, низкие остатки, ABC, оборачиваемость, экспорт."""
import io

from openpyxl import load_workbook

from tests.test_documents import _create_and_post, _make_item, _unit_id, _warehouse_id

# Период тестов — август 2026, даты уникальны в рамках сессии
DF, DT = "2026-08-01", "2026-08-31"

_scenario = None


def _sc(client, auth):
    """Сценарий: приход 100 → расход 30 → списание 5 → инвентаризация 65→60."""
    global _scenario
    if _scenario is not None:
        return _scenario
    unit = _unit_id(client, auth)
    wh = _warehouse_id(client, auth)
    item = _make_item(client, auth, "Отч-Товар-1", "REP-1")
    item2 = _make_item(client, auth, "Отч-Товар-2", "REP-2")
    item3 = _make_item(client, auth, "Отч-Товар-3", "REP-3")
    # Цена/минимум для проверок сумм и «низких остатков»
    for iid, patch in ((item, {"cost_price": 25, "min_qty": 10}),
                       (item3, {"min_qty": 5})):
        r = client.put(f"/api/items/{iid}", json={
            "name": client.get(f"/api/items/{iid}", headers=auth).json()["name"],
            "sku": client.get(f"/api/items/{iid}", headers=auth).json()["sku"],
            "unit_id": unit, **patch,
        }, headers=auth)
        assert r.status_code == 200, r.text
    _create_and_post(client, auth, "in", [{"item_id": item, "warehouse_to_id": wh, "qty": 100, "price": 25}], date="2026-08-01")
    _create_and_post(client, auth, "out", [{"item_id": item, "warehouse_from_id": wh, "qty": 30, "price": 40}], date="2026-08-10")
    _create_and_post(client, auth, "writeoff", [{"item_id": item, "warehouse_from_id": wh, "qty": 5}], reason="Брак", date="2026-08-15")
    _create_and_post(client, auth, "in", [{"item_id": item2, "warehouse_to_id": wh, "qty": 10, "price": 10}], date="2026-08-05")
    _create_and_post(client, auth, "out", [{"item_id": item2, "warehouse_from_id": wh, "qty": 10, "price": 100}], date="2026-08-20")
    r = client.post("/api/documents", json={
        "type": "inventory", "date": "2026-08-25", "warehouse_id": wh,
        "results": [{"item_id": item, "counted_qty": 60}],
    }, headers=auth)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert client.post(f"/api/documents/{doc['id']}/post", headers=auth).status_code == 200
    _scenario = {"item": item, "item2": item2, "item3": item3, "wh": wh}
    return _scenario


def _row_by_sku(data, sku, sku_col=1):
    match = [r for r in data["rows"] if r[sku_col] == sku]
    assert len(match) == 1, f"строка {sku}: {[r[:5] for r in data['rows']]}"
    return match[0]


def test_balance_on_date(client, auth):
    _sc(client, auth)
    # 01.08: +100, 10.08: −30 → на 12.08 = 70 (списание 15.08 ещё не произошло)
    data = client.get("/api/reports/balance?as_of=2026-08-12", headers=auth).json()
    row = _row_by_sku(data, "REP-1")
    assert row[5] == 70 and row[6] == 25 and row[7] == 1750  # кол-во, себестоимость, сумма
    row2 = _row_by_sku(data, "REP-2")
    assert row2[5] == 10
    # на 31.08: 70 − 5 (списание) − 5 (инвентаризация 65→60) = 60; REP-2 = 0 и скрывается
    data = client.get("/api/reports/balance?as_of=2026-08-31", headers=auth).json()
    assert _row_by_sku(data, "REP-1")[5] == 60
    assert not any(r[1] == "REP-2" for r in data["rows"])


def test_movement_report(client, auth):
    _sc(client, auth)
    # В строке движения: [дата, номер, тип, наименование, артикул, от, куда, кол-во, цена, сумма]
    data = client.get(f"/api/reports/movement?date_from={DF}&date_to={DT}&doc_type=in", headers=auth).json()
    row = _row_by_sku(data, "REP-1", sku_col=4)
    assert row[7] == 100 and row[9] == 2500  # +100, 100×25
    data = client.get(f"/api/reports/movement?date_from={DF}&date_to={DT}&doc_type=out&q=REP-1", headers=auth).json()
    assert _row_by_sku(data, "REP-1", sku_col=4)[7] == -30
    # Все типы за период, поиск по артикулу: +100 −30 −5 −5 (инвентаризация)
    data = client.get(f"/api/reports/movement?date_from={DF}&date_to={DT}&q=REP-1", headers=auth).json()
    signed = [r[7] for r in data["rows"]]
    assert signed == [100, -30, -5, -5]
    assert data["totals"][7] == 60


def test_turnover_report(client, auth):
    _sc(client, auth)
    data = client.get(f"/api/reports/turnover?date_from={DF}&date_to={DT}&q=REP-1", headers=auth).json()
    row = _row_by_sku(data, "REP-1")
    # нач 0, приход 100, расход 30, списание 5, инвентаризация −5 → кон 60
    assert row[4:10] == [0, 100, 30, 5, -5, 60]
    assert row[10] == 60 * 25  # сумма по себестоимости
    assert data["totals"] is not None and data["totals"][9] == 60


def test_below_min_report(client, auth):
    s = _sc(client, auth)
    data = client.get("/api/reports/below_min", headers=auth).json()
    rows = data["rows"]
    # item3: минимум 5, остатка нет → недостача 5; item1 (60 > 10) в отчёте не фигурирует
    assert any(r[1] == "REP-3" and r[6] == 5 for r in rows)
    assert not any(r[1] == "REP-1" for r in rows)
    assert data["totals"][6] >= 5


def test_abc_report(client, auth):
    _sc(client, auth)
    data = client.get(f"/api/reports/abc?date_from={DF}&date_to={DT}", headers=auth).json()
    r1 = _row_by_sku(data, "REP-1")  # 30 × 40 = 1200 из 2200 → 54,5 % → класс A
    r2 = _row_by_sku(data, "REP-2")  # 10 × 100 = 1000 → нараст. 100 % → класс C
    assert r1[3] == 1200 and r1[4] == 54.5 and r1[6] == "A"
    assert r2[3] == 1000 and r2[5] == 100.0 and r2[6] == "C"


def test_turnover_speed_report(client, auth):
    _sc(client, auth)
    data = client.get(f"/api/reports/turnover_speed?date_from={DF}&date_to={DT}", headers=auth).json()
    row = _row_by_sku(data, "REP-1")
    # средний остаток (0 + 60) / 2 = 30; дней в периоде 30; расход 30/30 = 1/день
    assert row[3] == 30 and row[4] == 30
    assert row[5] == 1                      # средний расход/день
    assert row[6] == 30                     # дней реализации
    assert row[7] == 1.0                    # оборачиваемость ≈ 1


def test_export_excel(client, auth):
    _sc(client, auth)
    r = client.get("/api/reports/balance/export?fmt=excel&as_of=2026-08-12", headers=auth)
    assert r.status_code == 200
    assert r.content[:2] == b"PK"  # .xlsx — это zip
    ws = load_workbook(io.BytesIO(r.content)).active
    flat = [[c for c in row] for row in ws.iter_rows(values_only=True)]
    text = str(flat)
    assert "Отч-Товар-1" in text and 70 in [v for row in flat for v in row if v is not None]


def test_export_pdf(client, auth):
    _sc(client, auth)
    r = client.get(f"/api/reports/abc/export?fmt=pdf&date_from={DF}&date_to={DT}", headers=auth)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"
    assert r.headers["content-disposition"].startswith("attachment")
