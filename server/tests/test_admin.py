"""Тесты раздела «Админ»: предприятие, пользователи, настройки, аудит, бэкап/восстановление."""


def test_company_update(client, auth):
    # Сохраняем исходные значения и возвращаем их в конце (БД общая для сессии)
    before = client.get("/api/company", headers=auth).json()
    r = client.put(
        "/api/company",
        json={"full_name": "ООО «Тестовая компания»", "inn_kpp": "7701234567/770101001", "phone": "+7 (495) 000-00-00"},
        headers=auth,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["full_name"] == "ООО «Тестовая компания»"
    assert body["inn_kpp"] == "7701234567/770101001"
    # Чтение без изменений работает
    got = client.get("/api/company", headers=auth).json()
    assert got["full_name"] == "ООО «Тестовая компания»"
    # Возврат исходного состояния
    client.put("/api/company", json={
        "full_name": before.get("full_name"),
        "inn_kpp": before.get("inn_kpp"),
        "phone": before.get("phone"),
    }, headers=auth)
    assert client.get("/api/company", headers=auth).json()["full_name"] == before.get("full_name")


def _login(client, username, password):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_users_crud(client, auth):
    # Создание
    r = client.post("/api/admin/users", json={
        "username": "sklad_rab", "password": "test1234", "full_name": "Раб Склад", "role": "user",
    }, headers=auth)
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    # Дубликат логина (с учётом регистра)
    r = client.post("/api/admin/users", json={
        "username": "SKLAD_RAB", "password": "test1234", "role": "user",
    }, headers=auth)
    assert r.status_code == 409
    # Список
    names = [u["username"] for u in client.get("/api/admin/users", headers=auth).json()]
    assert "sklad_rab" in names
    # Обновление: роль + пароль
    r = client.put(f"/api/admin/users/{uid}", json={"role": "admin", "password": "newpass1"}, headers=auth)
    assert r.status_code == 200
    assert r.json()["role"] == "admin"
    # Новый пароль работает для входа
    user_auth = _login(client, "sklad_rab", "newpass1")
    # Самоблокировка: нельзя сменить себе роль с admin
    r = client.put(f"/api/admin/users/{uid}", json={"role": "user"}, headers=user_auth)
    assert r.status_code == 400
    r = client.put(f"/api/admin/users/{uid}", json={"active": False}, headers=user_auth)
    assert r.status_code == 400
    # Обычный пользователь не заходит в Админ
    client.put(f"/api/admin/users/{uid}", json={"role": "user", "active": True}, headers=auth)
    user_auth = _login(client, "sklad_rab", "newpass1")
    r = client.get("/api/admin/users", headers=user_auth)
    assert r.status_code == 403
    r = client.put("/api/company", json={"full_name": "Взлом"}, headers=user_auth)
    assert r.status_code == 403


def test_settings(client, auth):
    r = client.get("/api/admin/settings", headers=auth)
    keys = {s["key"] for s in r.json()}
    assert keys == {"allow_negative_stock", "default_warehouse_id"}
    # Неизвестный ключ
    r = client.put("/api/admin/settings", json={"key": "bogus", "value": "1"}, headers=auth)
    assert r.status_code == 400
    # Смена и возврат
    r = client.put("/api/admin/settings", json={"key": "allow_negative_stock", "value": "true"}, headers=auth)
    assert r.status_code == 200 and r.json()["value"] == "true"
    vals = {s["key"]: s["value"] for s in client.get("/api/admin/settings", headers=auth).json()}
    assert vals["allow_negative_stock"] == "true"
    client.put("/api/admin/settings", json={"key": "allow_negative_stock", "value": "false"}, headers=auth)


def test_audit_list(client, auth):
    # После действий из предыдущих тестов в журнале уже есть записи
    r = client.get("/api/admin/audit", headers=auth)
    assert r.status_code == 200
    page = r.json()
    assert page["total"] >= 1
    assert page["rows"], "строки журнала пусты"
    row = page["rows"][0]
    for field in ("id", "ts", "action", "entity"):
        assert row[field] is not None
    # Фильтр по действию
    r = client.get("/api/admin/audit?action=update", headers=auth)
    assert all(row["action"] == "update" for row in r.json()["rows"])
    # Поиск по тексту (логин admin)
    r = client.get("/api/admin/audit?q=admin", headers=auth)
    assert r.json()["total"] >= 1
    # Пагинация
    r = client.get("/api/admin/audit?size=1&page=1", headers=auth)
    assert len(r.json()["rows"]) <= 1


def test_backup_download(client, auth):
    r = client.get("/api/admin/backup", headers=auth)
    assert r.status_code == 200
    assert r.content.startswith(b"SQLite format 3\x00")


def test_restore_roundtrip(client, auth):
    # Копия текущей базы
    backup_bytes = client.get("/api/admin/backup", headers=auth).content
    assert backup_bytes.startswith(b"SQLite format 3\x00")
    # Не-SQLite файл отклоняется
    r = client.post(
        "/api/admin/restore",
        files={"file": ("garbage.db", b"this is not sqlite", "application/octet-stream")},
        headers=auth,
    )
    assert r.status_code == 400
    # Восстановление из валидной копии — данные сохраняются
    before = client.get("/api/company", headers=auth).json()
    r = client.post(
        "/api/admin/restore",
        files={"file": ("sklad_backup.db", backup_bytes, "application/octet-stream")},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    # После замены БД логин работает, карточка предприятия не потеряна
    auth2 = _login(client, "admin", "1234")
    got = client.get("/api/company", headers=auth2).json()
    assert got["full_name"] == before["full_name"]
