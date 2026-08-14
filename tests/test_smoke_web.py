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
    c = app.test_client()
    c.post("/login", data={"password": app.config["APP_PASSWORD"]})
    return c


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
            "precio_venta_caja": "18000",  # 3000/unidad x 6 unidades/caja
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
            "precio_venta_caja": "36000",  # 3000/unidad x 12 unidades/caja
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    assert client.get("/productos/").status_code == 200
    assert client.get("/productos/inventario").status_code == 200

    # Carga masiva: una línea con descuento de referencia, otra sin (debe quedar en 0)
    r = client.post(
        "/productos/carga-masiva",
        data={"lineas": "Hit Mango 250ml; Jugo; 24; 1500; 8\nManzana Postobon 1.5L; Jugo; 6; 3200"},
        follow_redirects=True,
    )
    assert r.status_code == 200

    from models import Producto

    coca = Producto.query.filter_by(nombre="Coca-Cola 1.5L").first()
    agua = Producto.query.filter_by(nombre="Agua Cristal 600ml").first()
    hit = Producto.query.filter_by(nombre="Hit Mango 250ml").first()
    manzana = Producto.query.filter_by(nombre="Manzana Postobon 1.5L").first()
    assert hit.tasa_descuento_referencia == 8.0
    assert manzana.tasa_descuento_referencia == 0.0
    assert coca is not None and agua is not None
    # El precio se capturó por caja (18000/6 y 36000/12) y debe quedar guardado por unidad
    assert coca.precio_actual() == 3000
    assert agua.precio_actual() == 3000

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
        data={"fecha": HOY, "notas": "", f"regreso_cajas_{coca.id}": "0", f"regreso_unidades_{coca.id}": "6"},
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

    # Cartera: factura pendiente ligada a esa misma ruta
    assert client.get("/cartera/nueva").status_code == 200
    r = client.post(
        "/cartera/nueva",
        data={"cliente": "Tienda El Ahorro", "salida_id": str(salida.id), "fecha": HOY, "monto": "40000", "notas": ""},
        follow_redirects=True,
    )
    assert r.status_code == 200

    from models import FacturaCartera

    factura = FacturaCartera.query.filter_by(cliente="Tienda El Ahorro").first()
    assert factura is not None and factura.estado == "pendiente"

    from services.cartera import total_pendiente

    assert total_pendiente() == 40000

    r = client.post(f"/cartera/{factura.id}/marcar-pagada", follow_redirects=True)
    assert r.status_code == 200
    assert total_pendiente() == 0

    assert client.get("/cartera/").status_code == 200
    assert client.get(f"/camion/{salida.id}").status_code == 200

    # Cartera: deuda anterior al sistema, sin ruta ligada
    r = client.post(
        "/cartera/nueva",
        data={"cliente": "Tienda Vieja", "salida_id": "", "fecha": "2026-05-01", "monto": "120000", "notas": ""},
        follow_redirects=True,
    )
    assert r.status_code == 200

    factura_vieja = FacturaCartera.query.filter_by(cliente="Tienda Vieja").first()
    assert factura_vieja is not None and factura_vieja.salida_id is None
    assert total_pendiente() == 120000
    assert "Deuda anterior" in client.get("/cartera/").get_data(as_text=True)

    # Venta en bodega: 2 unidades de Agua Cristal (3000 COP c/u = 6000)
    assert client.get("/bodega/nueva").status_code == 200
    r = client.post(
        "/bodega/nueva",
        data={
            "fecha": HOY,
            "notas": "",
            "producto_id[]": [str(agua.id)],
            "cantidad[]": ["2"],
            "tipo_cantidad[]": ["unidad"],
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert calcular_stock(agua.id) == 1  # tenía 3 por el canje, vendió 2 en bodega
    assert client.get("/bodega/").status_code == 200

    # Recarga a camión: segunda salida, sin cerrar, para probar el flujo completo
    r = client.post(
        "/camion/salida/nueva",
        data={
            "fecha": HOY,
            "notas": "Ruta Sur",
            "producto_id[]": [str(coca.id)],
            "cantidad[]": ["2"],
            "tipo_cantidad[]": ["caja"],
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    salida2 = SalidaCamion.query.filter_by(notas="Ruta Sur").first()
    assert calcular_stock(coca.id) == 24  # 36 - 12 (2 cajas)

    assert client.get("/camion/recarga/nueva").status_code == 200
    assert client.get(f"/camion/recarga/nueva/{salida2.id}").status_code == 200
    r = client.post(
        f"/camion/recarga/nueva/{salida2.id}",
        data={
            "fecha": HOY,
            "notas": "",
            "producto_id[]": [str(coca.id)],
            "cantidad[]": ["1"],
            "tipo_cantidad[]": ["caja"],
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert calcular_stock(coca.id) == 18  # 24 - 6 (1 caja recargada)

    # Retorno de la segunda ruta: cargado total = 2 cajas + 1 recarga = 18u, regresan 0
    r = client.post(
        f"/camion/retorno/nueva/{salida2.id}",
        data={"fecha": HOY, "notas": "", f"regreso_cajas_{coca.id}": "0", f"regreso_unidades_{coca.id}": "0"},
        follow_redirects=True,
    )
    assert r.status_code == 200

    from services.ventas import venta_por_salida

    detalle2 = venta_por_salida(salida2.id)
    assert detalle2[0]["cantidad_vendida"] == 18  # 12 (salida) + 6 (recarga) - 0 (retorno)
