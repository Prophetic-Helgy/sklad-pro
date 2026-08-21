@echo off
rem Smoke-тест portable-сборки: запуск + автозакрытие после загрузки UI.
rem (только ASCII-паттерны: cmd не читает кириллицу в UTF-8 без BOM)
cd /d "%~dp0dist-electron"
for %%f in (*portable*.exe) do start /wait "" "%%f" --smoke
echo PORTABLE_SMOKE_EXIT=%errorlevel%
