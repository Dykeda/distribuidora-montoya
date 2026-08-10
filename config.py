import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
        BASE_DIR, "instance", "distribuidora.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # En el hosting en línea, SIEMPRE se debe fijar APP_PASSWORD y SECRET_KEY propios
    # como variables de entorno (ver DEPLOY.md). Estos valores por defecto solo son para
    # uso local con iniciar.bat, donde el único acceso al sistema es ese mismo computador.
    SECRET_KEY = os.environ.get("SECRET_KEY", "distribuidora-montoya-local")
    APP_PASSWORD = os.environ.get("APP_PASSWORD", "montoya2026")
