"""Конфигурация приложения «Склад ПРО».

Все пути и параметры можно переопределить переменными окружения:
- SKLAD_DATA_DIR — папка с базой и бэкапами (по умолчанию %LOCALAPPDATA%/SkladPro/data)
- SKLAD_PORT — порт HTTP-сервера (по умолчанию 8700)
- SKLAD_HOST — адрес привязки (по умолчанию 0.0.0.0, чтобы быть доступным в сети)
- SKLAD_SECRET_KEY — секрет JWT (если не задан — создаётся и хранится в data/secret.key)
"""
import os
import secrets
from pathlib import Path

APP_NAME = "Склад ПРО"
APP_VERSION = "1.0"

# Ключевые константы
PORT = int(os.environ.get("SKLAD_PORT", "8700"))
HOST = os.environ.get("SKLAD_HOST", "0.0.0.0")

def _default_data_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "SkladPro" / "data"
    return Path.home() / ".skladpro" / "data"

DATA_DIR = Path(os.environ.get("SKLAD_DATA_DIR", _default_data_dir()))
DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR = DATA_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "склад.db"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"


def get_secret_key() -> str:
    """Секрет JWT: из окружения или из файла secret.key (создаётся один раз)."""
    key = os.environ.get("SKLAD_SECRET_KEY")
    if key:
        return key
    key_file = DATA_DIR / "secret.key"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    key_file.write_text(key, encoding="utf-8")
    return key


SECRET_KEY = get_secret_key()
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 12
