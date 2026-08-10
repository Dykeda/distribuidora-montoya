@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Instalando Distribuidora Montoya...
echo ============================================

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
