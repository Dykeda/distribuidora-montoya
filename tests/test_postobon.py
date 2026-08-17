from datetime import date

import pytest

from models import Producto, ProductoPrecio, Compra, CompraDetalle
from services.postobon import listar_faltantes, listar_faltantes_agrupados


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"password": app.config["APP_PASSWORD"]})
    return c


def crear_producto(db, nombre="Coca-Cola 1.5L", precio=3000, tasa_referencia=10.0):
    p = Producto(nombre=nombre, unidades_por_caja=6, maneja_cajas=True, maneja_unidades=True, tasa_descuento_referencia=tasa_referencia)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, precio_venta_caja=precio * 6, vigente_desde=date(2026, 1, 1)))
    db.session.commit()
    return p


def crear_compra_detalle(db, producto, fecha, costo_linea, tasa_aplicada, cantidad=60, numero_factura="F-001"):
    compra = Compra(fecha=fecha, numero_factura=numero_factura)
    db.session.add(compra)
    db.session.flush()
    detalle = CompraDetalle(
        compra_id=compra.id, producto_id=producto.id, cantidad_comprada_unidades=cantidad,
        costo_linea=costo_linea, tasa_descuento_aplicada=tasa_aplicada,
    )
    db.session.add(detalle)
    db.session.commit()
    return compra, detalle


def test_listar_faltantes_detecta_tasa_aplicada_menor_a_la_esperada(db):
    coca = crear_producto(db, tasa_referencia=15.0)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0)

    filas = listar_faltantes(date(2026, 8, 1), date(2026, 8, 31))

    assert len(filas) == 1
    assert filas[0]["producto"] == coca
    assert filas[0]["tasa_esperada"] == 15.0
    assert filas[0]["tasa_aplicada"] == 10.0
    assert filas[0]["diferencia_pct"] == 5.0
    assert filas[0]["monto_faltante"] == 5000  # 100000 * 5% = 5000


def test_listar_faltantes_no_marca_cuando_aplico_la_tasa_esperada(db):
    coca = crear_producto(db, tasa_referencia=10.0)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0)

    assert listar_faltantes(date(2026, 8, 1), date(2026, 8, 31)) == []


def test_listar_faltantes_no_marca_cuando_aplico_mas_de_lo_esperado(db):
    coca = crear_producto(db, tasa_referencia=10.0)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=20.0)

    assert listar_faltantes(date(2026, 8, 1), date(2026, 8, 31)) == []


def test_listar_faltantes_ignora_fuera_del_periodo(db):
    coca = crear_producto(db, tasa_referencia=15.0)
    crear_compra_detalle(db, coca, date(2026, 5, 1), costo_linea=100000, tasa_aplicada=5.0)

    assert listar_faltantes(date(2026, 8, 1), date(2026, 8, 31)) == []


def test_listar_faltantes_ignora_compra_sin_numero_de_factura(db):
    # ej. carga de inventario físico de bodega, no una factura real de Postobón
    coca = crear_producto(db, tasa_referencia=15.0)
    crear_compra_detalle(db, coca, date(2026, 8, 16), costo_linea=100000, tasa_aplicada=0.0, numero_factura=None)

    assert listar_faltantes(date(2026, 8, 1), date(2026, 8, 31)) == []


def test_listar_faltantes_agrupados_agrupa_por_factura_con_subtotal(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", tasa_referencia=15.0)
    agua = crear_producto(db, "Agua Cristal", tasa_referencia=10.0)

    compra1 = Compra(fecha=date(2026, 8, 17), numero_factura="AS001")
    db.session.add(compra1)
    db.session.flush()
    db.session.add(CompraDetalle(compra_id=compra1.id, producto_id=coca.id, cantidad_comprada_unidades=60, costo_linea=100000, tasa_descuento_aplicada=10.0))
    db.session.add(CompraDetalle(compra_id=compra1.id, producto_id=agua.id, cantidad_comprada_unidades=60, costo_linea=50000, tasa_descuento_aplicada=5.0))
    db.session.commit()

    compra2, _ = crear_compra_detalle(db, coca, date(2026, 8, 18), costo_linea=200000, tasa_aplicada=5.0, numero_factura="AS002")

    grupos = listar_faltantes_agrupados(date(2026, 8, 1), date(2026, 8, 31))

    assert len(grupos) == 2
    # ordenado por fecha descendente -> AS002 primero
    assert grupos[0]["compra"].numero_factura == "AS002"
    assert grupos[0]["subtotal"] == 20000  # 200000 * 10%
    assert grupos[1]["compra"].numero_factura == "AS001"
    assert len(grupos[1]["lineas"]) == 2
    assert grupos[1]["subtotal"] == 5000 + 2500  # coca: 100000*5%, agua: 50000*5%


def test_pagina_informe_muestra_faltante_agrupado_y_total(db, client):
    coca = crear_producto(db, tasa_referencia=15.0)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0, numero_factura="AS07196376")

    r = client.get("/postobon/?anio=2026&mes=8")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Coca-Cola 1.5L" in body
    assert "AS07196376" in body
    assert "5,000" in body  # monto faltante


def test_pagina_informe_vacia_cuando_no_hay_faltantes(client):
    r = client.get("/postobon/?anio=2026&mes=8")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "No hay faltantes" in body


def test_exportar_excel_descarga_archivo(db, client):
    coca = crear_producto(db, tasa_referencia=15.0)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0)

    r = client.get("/postobon/exportar-excel?anio=2026&mes=8")
    assert r.status_code == 200
    assert r.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in r.headers.get("Content-Disposition", "")


def test_detalle_de_compra_resalta_fila_con_faltante(db, client):
    coca = crear_producto(db, tasa_referencia=15.0)
    compra, _ = crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0)

    r = client.get(f"/compras/{compra.id}")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "table-danger" in body
    assert "esperado 15.0%" in body


def test_detalle_de_compra_no_resalta_fila_sin_faltante(db, client):
    coca = crear_producto(db, tasa_referencia=10.0)
    compra, _ = crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0)

    r = client.get(f"/compras/{compra.id}")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "table-danger" not in body
