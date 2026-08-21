"""Наполнение dev-базы данными для скриншотов (одноразовый скрипт)."""
import httpx

B = "http://127.0.0.1:8700"
c = httpx.Client(timeout=30)

r = c.post(f"{B}/api/auth/login", json={"username": "admin", "password": "1234"})
r.raise_for_status()
H = {"Authorization": f"Bearer {r.json()['access_token']}"}


def get(path):
    r = c.get(B + path, headers=H)
    r.raise_for_status()
    return r.json()


def post(path, body=None):
    r = c.post(B + path, json=body, headers=H)
    if r.status_code >= 400:
        raise RuntimeError(f"{path}: {r.status_code} {r.text}")
    return r.json()


def put(path, body):
    r = c.put(B + path, json=body, headers=H)
    if r.status_code >= 400:
        raise RuntimeError(f"{path}: {r.status_code} {r.text}")
    return r.json()


# --- Справочники -------------------------------------------------------------
cats = {x["name"]: x["id"] for x in get("/api/categories")}
for name in ("Метизы", "Крепёж", "Фасовка"):
    if name not in cats:
        cats[name] = post("/api/categories", {"name": name})["id"]

units = {x["name"]: x["id"] for x in get("/api/units")}
U_SHT, U_UP = units["шт"], units["уп"]

partners = {x["full_name"]: x["id"] for x in get("/api/partners")}
p_str = partners.get("ООО «СтройБаз»") or post("/api/partners", {
    "kind": "supplier", "full_name": "ООО «СтройБаз»", "short_name": "СтройБаз",
    "legal_address": "г. Москва, ул. Промышленная, д. 12", "phone": "+7 (495) 123-45-67",
    "email": "sales@stroybaz.ru", "inn": "7723456789", "ogrn": "1157746123456",
})["id"]
p_kov = partners.get("ИП Ковалёв А.С.") or post("/api/partners", {
    "kind": "customer", "full_name": "ИП Ковалёв А.С.", "short_name": "Ковалёв",
    "phone": "+7 (916) 555-44-33", "inn": "502412345678",
})["id"]

wh = {x["name"]: x["id"] for x in get("/api/warehouses")}
wh_rzv = wh.get("Резерв") or post("/api/warehouses", {"name": "Резерв"})["id"]

# --- Товары ------------------------------------------------------------------
ITEMS = [
    # имя, артикул, штрих-код, ед, категория, min, себест, цена
    ("Болт М8", "B-M8", "4600000000017", U_SHT, "Метизы", 20, 1.10, 2.20),
    ("Гайка М8", "G-M8", "4600000000024", U_SHT, "Метизы", 30, 0.45, 0.90),
    ("Шайба 8", "W-8", "4600000000031", U_SHT, "Метизы", 50, 0.25, 0.60),
    ("Сухарь М8", "L-M8", None, U_SHT, "Метизы", 200, 0.60, 1.30),
    ("Саморез 4.2×25", "SR-4225", "4600000000048", U_UP, "Метизы", 5, 35.0, 62.0),
    ("Дюбель 6×40", "D-640", "4600000000055", U_UP, "Крепёж", 3, 9.0, 16.0),
    ("Хомут 19", "H-19", None, U_SHT, "Крепёж", 10, 7.5, 14.0),
    ("Кронштейн 80", "BR-80", None, U_SHT, "Крепёж", 5, 110.0, 195.0),
]
item_id = {}
for name, sku, barcode, unit, cat, minq, cost, price in ITEMS:
    body = {"name": name, "sku": sku, "barcode": barcode, "unit_id": unit,
            "category_id": cats[cat], "min_qty": minq, "cost_price": cost,
            "sale_price": price, "default_partner_id": p_str}
    item_id[name] = post("/api/items", body)["id"]

me = get("/api/auth/me")
admin_id = me["id"]

# --- Документы ---------------------------------------------------------------
def doc(type_, date, items, **kw):
    d = post("/api/documents", {"type": type_, "date": date, "items": items, **kw})
    return post(f"/api/documents/{d['id']}/post")["id"]

IN1, IN2, IN3, IN4 = "Болт М8", "Гайка М8", "Шайба 8", "Сухарь М8"

doc("in", "2026-08-10",
    [{"item_id": item_id[IN1], "warehouse_to_id": wh["Основной"], "qty": 200, "price": 1.10},
     {"item_id": item_id[IN2], "warehouse_to_id": wh["Основной"], "qty": 300, "price": 0.45},
     {"item_id": item_id[IN3], "warehouse_to_id": wh["Основной"], "qty": 400, "price": 0.25},
     {"item_id": item_id[IN4], "warehouse_to_id": wh["Основной"], "qty": 150, "price": 0.60}],
    partner_id=p_str, doc_ref="Н-101")

doc("in", "2026-08-15",
    [{"item_id": item_id["Саморез 4.2×25"], "warehouse_to_id": wh["Основной"], "qty": 20, "price": 35.0},
     {"item_id": item_id["Дюбель 6×40"], "warehouse_to_id": wh["Основной"], "qty": 15, "price": 9.0},
     {"item_id": item_id["Хомут 19"], "warehouse_to_id": wh["Основной"], "qty": 60, "price": 7.5},
     {"item_id": item_id["Кронштейн 80"], "warehouse_to_id": wh["Основной"], "qty": 10, "price": 110.0}],
    partner_id=p_str, doc_ref="Н-102")

doc("out", "2026-08-12",
    [{"item_id": item_id[IN1], "warehouse_from_id": wh["Основной"], "qty": 40},
     {"item_id": item_id[IN2], "warehouse_from_id": wh["Основной"], "qty": 40},
     {"item_id": item_id[IN3], "warehouse_from_id": wh["Основной"], "qty": 60}],
    doc_ref="Р-201", out_by_id=admin_id, received_by="ИП Ковалёв А.С.")

doc("out", "2026-08-18",
    [{"item_id": item_id["Саморез 4.2×25"], "warehouse_from_id": wh["Основной"], "qty": 2},
     {"item_id": item_id["Кронштейн 80"], "warehouse_from_id": wh["Основной"], "qty": 5},
     {"item_id": item_id["Хомут 19"], "warehouse_from_id": wh["Основной"], "qty": 12}],
    doc_ref="Р-207", out_by_id=admin_id, received_by="ИП Ковалёв А.С.")

doc("writeoff", "2026-08-19",
    [{"item_id": item_id["Дюбель 6×40"], "warehouse_from_id": wh["Основной"], "qty": 1},
     {"item_id": item_id["Хомут 19"], "warehouse_from_id": wh["Основной"], "qty": 2}],
    partner_id=p_str, reason="Повреждение при транспортировке")

doc("transfer", "2026-08-20",
    [{"item_id": item_id[IN1], "warehouse_from_id": wh["Основной"], "warehouse_to_id": wh_rzv, "qty": 50},
     {"item_id": item_id[IN2], "warehouse_from_id": wh["Основной"], "warehouse_to_id": wh_rzv, "qty": 100}])

doc("inventory", "2026-08-21", [],
    warehouse_id=wh["Основной"],
    results=[{"item_id": item_id[IN1], "counted_qty": 110},
             {"item_id": item_id["Кронштейн 80"], "counted_qty": 4},
             {"item_id": item_id["Хомут 19"], "counted_qty": 46}])

# --- Карточка предприятия + пользователь -------------------------------------
put("/api/company", {
    "full_name": "ООО «СтройКомплект»", "short_name": "СтройКомплект",
    "legal_address": "г. Москва, ул. Складская, д. 7, стр. 2",
    "postal_address": "115280, г. Москва, ул. Складская, д. 7",
    "phone": "+7 (495) 789-12-34", "email": "info@stroykomplekt.ru",
    "inn_kpp": "7725881234 / 772501001", "ogrn": "1177746987654",
    "director": "Петров Иван Сергеевич", "bank": "АО «ПромБанк», г. Москва",
    "bik": "044525225", "account": "40702810400000012345",
    "corr_account": "30101810400000000225",
})
post("/api/admin/users", {"username": "kassir", "password": "kassa-2026",
                          "full_name": "Мария Соколова", "role": "user"})

stock = get("/api/stock?size=100")
rows = stock["rows"] if "rows" in stock else stock
print("Остатки:")
for s in (rows if isinstance(rows, list) else []):
    print(f"  {s.get('item_name') or s.get('name')}: {s.get('qty')}")
print("Готово.")
