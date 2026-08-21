@echo off
rem ============================================================
rem  Склад ПРО — запуск в режиме разработки (две консоли)
rem  Сервер:  http://127.0.0.1:8700  (API)
rem  Интерфейс: http://127.0.0.1:5173 (vite, прокси /api)
rem ============================================================
set SKLAD_DATA_DIR=%~dp0data\dev

cd /d "%~dp0server"
echo Запуск сервера (8700)...
start "Склад ПРО - сервер" cmd /k "set SKLAD_DATA_DIR=%~dp0data\dev^& python -m uvicorn app.main:app --port 8700 --reload"

timeout /t 2 /nobreak >nul

cd /d "%~dp0web"
echo Запуск интерфейса (5173)...
start "Склад ПРО - интерфейс" cmd /k "npm run dev"

echo.
echo Откройте в браузере: http://127.0.0.1:5173  (admin / 1234)
pause
