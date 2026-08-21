"""Тестовые фикстуры: изолированная БД на сессию + клиент FastAPI."""
import os
import tempfile

# ВАЖНО: до импорта app — тестовая папка данных (иначе создастся реальная)
_tmp = tempfile.mkdtemp(prefix="sklad-test-")
os.environ["SKLAD_DATA_DIR"] = os.path.join(_tmp, "data")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import seed  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    """TestClient с заполненной БД (admin, склад, ед. изм)."""
    Base.metadata.create_all(engine)
    seed.seed()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth(client):
    """Заголовки с токеном администратора."""
    r = client.post("/api/auth/login", json={"username": "admin", "password": "1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
