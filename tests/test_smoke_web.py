"""Smoke test: recorre las pantallas principales end-to-end usando el test client de Flask,
sin necesidad de un navegador real. No es parte de la suite de negocio (Fase 2), es una
verificación de integración de las rutas/plantillas (Fase 8).

Todas las fechas de las transacciones usan HOY o después, porque el precio de un producto
solo empieza a existir el día en que se crea (historial de precios) — una compra fechada
antes de que el producto exista no puede valorizarse, por diseño (precio histórico)."""
from datetime import date

import pytest

HOY = date.today().isoformat()


@pytest.fixture
def client(app):
    return app.test_client()


def test_flujo_completo(client):
    # Dashboard vacío
    assert client.get("/").status_code == 200

    # Crear productos
    r = client.post(
        "/productos/nuevo",
        data={
            "nombre": "Coca-Cola 1.5L",
            "categoria": "Gaseosa",
            "unidades_por_caja": "6",
            "maneja_cajas": "on",
            "maneja_unidades": "on",
            "precio_venta_unidad": "3000",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    r = client.post(
        "/productos/nuevo",
        data={
            "nombre": "Agua Cristal 600ml",
            "categoria": "Agua",
            "unidades_por_caja": "12",
            "maneja_cajas": "on",
            "maneja_unidades": "on",
            "precio_venta_unidad": "3000",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    assert client.get("/productos/").status_code == 200
    assert client.get("/productos/inventario").status_code == 200

    # Carga masiva
    r = client.post(
        "/productos/carga-masiva",
        data={"lineas": "Hit Mango 250ml; Jugo; 24; 1500\nManzana Postobon 1.5L; Jugo; 6; 3200"},
        follow_redirects=True,
    )
    assert r.status_code == 200

    from models import Producto

    coca = Producto.query.filter_by(nombre="Coca-Cola 1.5L").first()
    agua = Producto.query.filter_by(nombre="Agua Cristal 600ml").first()
    assert coca is not None and agua is not None

    # Registrar compra: 10 cajas (60u) de Coca-Cola, 180000 COP, 5% descuento
    r = client.post(
        "/compras/nueva",
        data={
            "fecha": HOY,
            "numero_factura": "F-001",
            "notas": "",
            "producto_id[]": [str(coca.id)],
            "cantidad[]": ["10"],
            "tipo_cantidad[]": ["caja"],
            "costo_linea[]": ["180000"],
            "tasa_descuento[]": ["5"],
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert client.get("/compras/").status_code == 200

    from services.inventario import calcular_stock

    assert calcular_stock(coca.id) == 60

    # Salida de camión: 5 cajas (30u)
    r = client.post(
        "/camion/salida/nueva",
        data={
            "fecha": HOY,
            "notas": "",
            "producto_id[]": [str(coca.id)],
            "cantidad[]": ["5"],
            "tipo_cantidad[]": ["caja"],
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert calcular_stock(coca.id) == 30

    from models import SalidaCamion

    salida = SalidaCamion.query.first()
    assert client.get(f"/camion/retorno/nueva/{salida.id}").status_code == 200

    # Retorno: 6 unidades sin vender
    r = client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={"fecha": HOY, "notas": "", f"regreso_{coca.id}": "6"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert calcular_stock(coca.id) == 36

    # Canje de descuento: 3 unidades de Agua Cristal (9000 COP exacto)
    r = client.post(
        "/descuentos/canje/nuevo",
        data={
            "fecha": HOY,
            "notas": "",
            "producto_id[]": [str(agua.id)],
            "cantidad[]": ["3"],
            "tipo_cantidad[]": ["unidad"],
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert calcular_stock(agua.id) == 3
    assert client.get("/descuentos/").status_code == 200

    # Reportes y dashboard reflejan el mes actual
    hoy = date.today()
    r = client.get(f"/reportes/?anio={hoy.year}&mes={hoy.month}")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "180,000" in body  # compra total
    assert "9,000" in body  # credito generado / canjeado
    assert "72,000" in body  # venta total

    assert client.get("/camion/").status_code == 200
    assert client.get(f"/camion/{salida.id}").status_code == 200
