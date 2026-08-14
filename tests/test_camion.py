from datetime import date

import pytest

from models import Producto, ProductoPrecio, SalidaCamion, SalidaCamionDetalle
from services.inventario import calcular_stock

HOY = date.today().isoformat()


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"password": app.config["APP_PASSWORD"]})
    return c


def crear_producto(db, nombre="Coca-Cola 1.5L", precio=3000, unidades_por_caja=6):
    p = Producto(nombre=nombre, unidades_por_caja=unidades_por_caja, maneja_cajas=True, maneja_unidades=True)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, precio_venta_caja=precio * unidades_por_caja, vigente_desde=date(2026, 1, 1)))
    db.session.commit()
    return p


def test_retorno_combina_cajas_y_unidades_sueltas(db, client):
    # Sale 1 caja de 6 = 60 unidades (10 cajas), regresan 3 cajas + 5 unidades sueltas
    coca = crear_producto(db, unidades_por_caja=6)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=60))
    db.session.commit()

    r = client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={
            "fecha": HOY, "notas": "",
            f"regreso_cajas_{coca.id}": "3",
            f"regreso_unidades_{coca.id}": "5",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    from models import RetornoCamion

    retorno = RetornoCamion.query.filter_by(salida_id=salida.id).first()
    assert retorno is not None
    # 3 cajas * 6 + 5 sueltas = 23 unidades regresadas
    assert retorno.detalles[0].cantidad_unidades == 23
    # stock = comprado(0) - salido(60) + regresado(23) = -37 (sin compra previa, solo interesa el movimiento)
    assert calcular_stock(coca.id) == -37


def test_retorno_no_permite_mas_de_lo_cargado(db, client):
    coca = crear_producto(db, unidades_por_caja=6)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=12))
    db.session.commit()

    # 3 cajas * 6 = 18, mas de lo cargado (12) -> debe rechazarse
    r = client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={"fecha": HOY, "notas": "", f"regreso_cajas_{coca.id}": "3", f"regreso_unidades_{coca.id}": "0"},
        follow_redirects=True,
    )
    assert r.status_code == 200

    from models import RetornoCamion

    assert RetornoCamion.query.filter_by(salida_id=salida.id).first() is None
