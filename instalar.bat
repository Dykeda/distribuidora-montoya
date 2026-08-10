@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Instalando Distribuidora Montoya...
echo ============================================

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo No se encontro Python instalado en este computador.
    echo.
    echo Antes de continuar, instala Python:
    echo   1. Ve a https://www.python.org/downloads/
    echo   2. Descarga e instala la version para Windows.
    echo   3. IMPORTANTE: en el instalador, marca la casilla que dice
    echo      "Add Python to PATH" antes de darle a Instalar.
    echo   4. Cuando termine, vuelve a hacer doble clic en este archivo.
    echo.
    pause
    exit /b 1
)

if not exist venv (
    echo Creando entorno virtual de Python...
    python -m venv venv
)

echo Instalando dependencias...
call venv\Scripts\pip.exe install --quiet -r requirements.txt

echo Preparando base de datos...
call venv\Scripts\python.exe -c "from app import app; from extensions import db; app.app_context().push(); db.create_all(); print('Base de datos lista.')"

echo.
echo ============================================
echo  Instalacion completa.
echo  Ahora puedes usar "iniciar.bat" para abrir el sistema.
echo ============================================
pause
