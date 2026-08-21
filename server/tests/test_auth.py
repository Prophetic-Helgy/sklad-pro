"""Тесты авторизации (Фаза 1)."""


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["name"] == "Склад ПРО"


def test_login_ok(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "1234"})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_bad_password(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/api/auth/login", json={"username": "ghost", "password": "x"})
    assert r.status_code == 401


def test_me(client, auth):
    r = client.get("/api/auth/me", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"


def test_me_no_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_user_list(client, auth):
    r = client.get("/api/auth/users", headers=auth)
    assert r.status_code == 200
    assert any(u["username"] == "admin" for u in r.json())
