# -*- mode: python ; coding: utf-8 -*-
# Склад ПРО — сервер (FastAPI + SQLite) → склад-server.exe (onedir).
# Сборка из папки server/:
#   python -m PyInstaller --noconfirm --distdir dist --workpath build/pis ../packaging/sklad-server.spec
# Итог: server/dist/sklad-server/sklad-server.exe (+ _internal/).
# Фронтенд (web/dist) НЕ вшивается: кладётся рядом, сервер находит его по
# SKLAD_DIST_DIR или по <каталог exe>/web/dist.

import os

from PyInstaller.utils.hooks import collect_submodules

# spec лежит в packaging/, сервер — в соседнем server/
SERVER_DIR = os.path.normpath(os.path.join(SPECPATH, '..', 'server'))

a = Analysis(
    [os.path.join(SERVER_DIR, 'server_entry.py')],
    pathex=[SERVER_DIR],
    binaries=[],
    datas=[],
    # Роутеры импортируются в app/api/__init__.py, но на всякий случай — все подмодули.
    hiddenimports=collect_submodules('app') + [
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan.on',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='sklad-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # логи видны в консоли; Electron перенаправит в файл
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='sklad-server',
)
