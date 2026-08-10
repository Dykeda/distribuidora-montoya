"""Copia la base de datos a una carpeta de respaldo con fecha y hora en el nombre.
Si el equipo tiene OneDrive, el respaldo queda ahí (se sincroniza solo a la nube).
Si no, se guarda en una carpeta local "respaldos" dentro del proyecto."""
import os
import shutil
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ORIGEN = os.path.join(BASE_DIR, "instance", "distribuidora.db")

onedrive = os.environ.get("OneDrive")
if onedrive and os.path.isdir(onedrive):
    DESTINO_DIR = os.path.join(onedrive, "Respaldos Distribuidora Montoya")
else:
    DESTINO_DIR = os.path.join(BASE_DIR, "respaldos")

if __name__ == "__main__":
    if not os.path.isfile(ORIGEN):
        print("No se encontró la base de datos todavía (instance/distribuidora.db).")
        print("Corre primero instalar.bat o iniciar.bat.")
        raise SystemExit(1)

    os.makedirs(DESTINO_DIR, exist_ok=True)
    marca = datetime.now().strftime("%Y-%m-%d_%H%M")
    destino = os.path.join(DESTINO_DIR, f"distribuidora_{marca}.db")
    shutil.copy2(ORIGEN, destino)

    print("Respaldo guardado en:")
    print(destino)
