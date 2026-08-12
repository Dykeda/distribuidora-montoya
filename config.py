import os
import sys

# Cuando corre empaquetado con PyInstaller (--onefile), los recursos incluidos
# (templates/, static/) quedan en una carpeta temporal (sys._MEIPASS), pero los datos
# que se deben conservar entre usos (la base de datos) tienen que vivir junto al .exe
# real, no en esa carpeta temporal que se borra al cerrar el programa.
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
    DATA_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATA_DIR = BASE_DIR

os.makedirs(os.path.join(DATA_DIR, "instance"), exist_ok=True)


class Config:
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
        DATA_DIR, "instance", "distribuidora.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # En el hosting en línea, SIEMPRE se debe fijar APP_PASSWORD y SECRET_KEY propios
    # como variables de entorno (ver DEPLOY.md). Estos valores por defecto solo son para
    # uso local con iniciar.bat, donde el único acceso al sistema es ese mismo computador.
    SECRET_KEY = os.environ.get("SECRET_KEY", "distribuidora-montoya-local")
    APP_PASSWORD = os.environ.get("APP_PASSWORD", "montoya2026")
    # Solo en true en el VPS (donde Certbot da HTTPS real) — con esto el navegador nunca
    # manda la cookie de sesión sin cifrar. Debe quedar en false para el uso local
    # (iniciar.bat/.exe corren en http://127.0.0.1, una cookie "Secure" ahí nunca se
    # enviaría y el login no funcionaría).
    SESSION_COOKIE_SECURE = os.environ.get("FORZAR_HTTPS", "false").lower() == "true"
