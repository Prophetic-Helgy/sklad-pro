@echo off
rem ============================================================
rem  Склад ПРО — полная сборка дистрибутива
rem  Нужно: Python 3.14 (pip install -r server\requirements.txt, pyinstaller),
rem         Node.js (npm)
rem  Результат: packaging\electron\dist-electron\
rem    - Склад ПРО portable 1.0.0.exe  (портативный)
rem    - Склад ПРО Setup 1.0.0.exe     (установщик)
rem ============================================================
setlocal
cd /d "%~dp0.."

echo [1/3] Сборка интерфейса (web/dist)...
pushd web
call npm run build || goto :err
popd

echo [2/3] Сборка сервера (server/dist/sklad-server)...
pushd server
call python -m PyInstaller --noconfirm --distpath dist --workpath build/pis ..\packaging\sklad-server.spec || goto :err
popd

echo [3/3] Сборка дистрибутива (portable + nsis)...
pushd packaging\electron
call npm install --no-audit --no-fund || goto :err
call npx electron-builder --win --x64 || goto :err
popd

echo.
echo Готово: packaging\electron\dist-electron\
exit /b 0

:err
echo.
echo Ошибка сборки (код %errorlevel%)
exit /b 1
