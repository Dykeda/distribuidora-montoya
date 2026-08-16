from datetime import date

import pytest

from models import Producto, ProductoPrecio, Compra, CompraDetalle
from services.descuentos import credito_generado_periodo
from services.inventario import calcular_stock


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"password": app.config["APP_PASSWORD"]})
    return c


def crear_producto(db, nombre="Coca-Cola 1.5L", precio=3000):
    p = Producto(nombre=nombre, unidades_por_caja=6, maneja_cajas=True, maneja_unidades=True)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, precio_venta_caja=precio * 6, vigente_desde=date(2026, 1, 1)))
    db.session.commit()
    return p


def test_eliminar_compra_borra_sus_lineas_y_recalcula_credito_e_inventario(db, client):
    coca = crear_producto(db)
    compra = Compra(fecha=date(2026, 8, 5), numero_factura="F-001")
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=60,
            costo_linea=180000, tasa_descuento_aplicada=5.0,
        )
    )
    db.session.commit()
    compra_id = compra.id

    assert credito_generado_periodo(date(2026, 8, 1), date(2026, 8, 31)) == 9000
    assert calcular_stock(coca.id) == 60

    r = client.post(f"/compras/{compra_id}/eliminar", follow_redirects=True)
    assert r.status_code == 200

    assert Compra.query.get(compra_id) is None
    assert CompraDetalle.query.filter_by(compra_id=compra_id).count() == 0
    assert credito_generado_periodo(date(2026, 8, 1), date(2026, 8, 31)) == 0
    assert calcular_stock(coca.id) == 0


def test_eliminar_compra_inexistente_da_404(client):
    assert client.post("/compras/999/eliminar").status_code == 404


def test_nueva_compra_combina_cajas_y_unidades_sueltas(db, client):
    coca = crear_producto(db)  # 6 unidades por caja

    r = client.post(
        "/compras/nueva",
        data={
            "fecha": "2026-08-16",
            "numero_factura": "",
            "notas": "",
            "producto_id[]": [str(coca.id)],
            "cajas[]": ["2"],
            "unidades[]": ["3"],
            "costo_linea[]": ["45000"],
            "tasa_descuento[]": ["0"],
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert calcular_stock(coca.id) == 15  # 2*6 + 3
