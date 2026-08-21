"""Точка входа FastAPI «Склад ПРО».

Раздаёт:
- /api/* — API (JSON)
- /      — собранный React-интерфейс (если web/dist существует)
"""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """При старте: таблицы + базовые данные (идемпотентно, работает и в exe)."""
    from .seed import seed
    seed()
    yield


app = FastAPI(title=config.APP_NAME, version=config.APP_VERSION, lifespan=lifespan)

# CORS: dev-режим (vite dev server) и сетевые клиенты
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health", tags=["Служебное"])
def health():
    return {"status": "ok", "name": config.APP_NAME, "version": config.APP_VERSION}


# Статика: собранный фронтенд (web/dist) — для продакшена и desktop-оболочки.
# Глубокие ссылки SPA (/login, /items...) отдаются через index.html (history fallback).
def _dist_dir() -> Path:
    """Путь к dist: SKLAD_DIST_DIR (Electron) → рядом с exe → web/dist (dev)."""
    env = os.environ.get("SKLAD_DIST_DIR")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):  # PyInstaller
        return Path(sys.executable).resolve().parent / "web" / "dist"
    return Path(__file__).resolve().parent.parent.parent / "web" / "dist"


dist_dir = _dist_dir()
if dist_dir.exists():
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file_path = (dist_dir / path).resolve()
        # защищаемся от выхода за пределы dist
        if path and file_path.is_file() and str(file_path).startswith(str(dist_dir.resolve())):
            return FileResponse(file_path)
        return FileResponse(dist_dir / "index.html")


def run():
    """Запуск сервера (используется склад-server.exe)."""
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="warning")


if __name__ == "__main__":
    run()
