@echo off
setlocal
cd /d "%~dp0"

echo Actualizando respaldo local (base de datos + Excel) desde el servidor...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0actualizar_respaldo.ps1"
echo.
pause
