@echo off
setlocal
cd /d "%~dp0"

if not exist venv (
    echo No se encontro el entorno instalado.
    echo Por favor corre primero "instalar.bat".
    pause
    exit /b 1
)

echo Haciendo respaldo de la base de datos...
call venv\Scripts\python.exe respaldar.py
echo.
pause
