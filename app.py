import webbrowser
from threading import Timer

from flask import Flask

from config import Config
from extensions import db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    from routes.dashboard import bp as dashboard_bp
    from routes.productos import bp as productos_bp
    from routes.compras import bp as compras_bp
    from routes.camion import bp as camion_bp
    from routes.descuentos import bp as descuentos_bp
    from routes.reportes import bp as reportes_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(productos_bp)
    app.register_blueprint(compras_bp)
    app.register_blueprint(camion_bp)
    app.register_blueprint(descuentos_bp)
    app.register_blueprint(reportes_bp)

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
    app.run(debug=True, use_reloader=False)
