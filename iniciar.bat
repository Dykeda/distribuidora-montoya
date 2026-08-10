@echo off
setlocal
cd /d "%~dp0"

if not exist venv (
    echo No se encontro el entorno instalado.
    echo Por favor corre primero "instalar.bat".
    pause
    exit /b 1
)

echo Iniciando Distribuidora Montoya...
echo Se abrira en tu navegador. No cierres esta ventana mientras la uses.
call venv\Scripts\python.exe app.py
pause
