@echo off
setlocal
cd /d "%~dp0"

echo Haciendo respaldo de la base de datos...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0respaldar.ps1"
echo.
pause
