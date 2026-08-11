import os
import sys
import webbrowser
from datetime import timedelta
from threading import Timer

from flask import Flask, session, redirect, url_for, request

from config import Config, BASE_DIR
from extensions import db

CONGELADO = getattr(sys, "frozen", False)


def create_app(config_overrides=None):
    if CONGELADO:
        # PyInstaller extrae templates/ y static/ a la carpeta temporal BASE_DIR;
        # sin esto, Flask buscaría esas carpetas junto al .exe y no las encontraría.
        app = Flask(
            __name__,
            template_folder=os.path.join(BASE_DIR, "templates"),
            static_folder=os.path.join(BASE_DIR, "static"),
        )
    else:
        app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        # Debe aplicarse ANTES de db.init_app(): Flask-SQLAlchemy fija el engine con la
        # config vigente en ese momento, así que cambiar SQLALCHEMY_DATABASE_URI después
        # no lo mueve — las pruebas terminarían leyendo/escribiendo la base de datos real
        # en vez de la de pruebas en memoria.
        app.config.update(config_overrides)
    app.permanent_session_lifetime = timedelta(days=30)
    db.init_app(app)

    from routes.auth import bp as auth_bp
    from routes.dashboard import bp as dashboard_bp
    from routes.productos import bp as productos_bp
    from routes.compras import bp as compras_bp
    from routes.camion import bp as camion_bp
    from routes.bodega import bp as bodega_bp
    from routes.descuentos import bp as descuentos_bp
    from routes.cartera import bp as cartera_bp
    from routes.reportes import bp as reportes_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(productos_bp)
    app.register_blueprint(compras_bp)
    app.register_blueprint(camion_bp)
    app.register_blueprint(bodega_bp)
    app.register_blueprint(descuentos_bp)
    app.register_blueprint(cartera_bp)
    app.register_blueprint(reportes_bp)

    @app.before_request
    def exigir_login():
        if request.endpoint in (None, "auth.login") or request.path.startswith("/static/"):
            return None
        if not session.get("autenticado"):
            return redirect(url_for("auth.login", next=request.path))

    @app.cli.command("init-db")
    def init_db():
        """Crea todas las tablas si no existen. Uso: flask --app app init-db"""
        with app.app_context():
            db.create_all()
        print("Base de datos inicializada.")

    return app


app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    def abrir_navegador():
        webbrowser.open("http://127.0.0.1:5000")

    Timer(1.0, abrir_navegador).start()
    app.run(debug=not CONGELADO, use_reloader=False)
