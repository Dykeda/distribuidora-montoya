from datetime import date

import pytest

from models import Producto, ProductoPrecio, Compra, CompraDetalle
from services.descuentos import (
    total_descuento_periodo,
    total_descuento_total_hasta,
    listar_descuentos_agrupados,
    rendimiento_por_producto,
)


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"password": app.config["APP_PASSWORD"]})
    return c


def crear_producto(db, nombre, precio):
    p = Producto(nombre=nombre, unidades_por_caja=6, maneja_cajas=True, maneja_unidades=True)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, precio_venta_caja=precio * 6, vigente_desde=date(2026, 1, 1)))
    db.session.commit()
    return p


def crear_compra_detalle(db, producto, fecha, costo_linea, cantidad=60, es_descuento=True, numero_factura="AS001"):
    compra = Compra(fecha=fecha, numero_factura=numero_factura)
    db.session.add(compra)
    db.session.flush()
    detalle = CompraDetalle(
        compra_id=compra.id, producto_id=producto.id, cantidad_comprada_unidades=cantidad,
        costo_linea=costo_linea, tasa_descuento_aplicada=0.0, es_descuento=es_descuento,
    )
    db.session.add(detalle)
    db.session.commit()
    return compra, detalle


def test_total_descuento_periodo_suma_solo_lineas_marcadas(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, es_descuento=True)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=50000, es_descuento=False)

    assert total_descuento_periodo(date(2026, 8, 1), date(2026, 8, 31)) == 100000


def test_total_descuento_total_hasta_es_historico(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    crear_compra_detalle(db, coca, date(2026, 5, 1), costo_linea=40000, es_descuento=True)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=60000, es_descuento=True)

    assert total_descuento_total_hasta(date(2026, 8, 31)) == 100000
    assert total_descuento_total_hasta(date(2026, 6, 30)) == 40000


def test_listar_descuentos_agrupados_por_factura_con_subtotal(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    agua = crear_producto(db, "Agua Cristal", 2000)

    compra1 = Compra(fecha=date(2026, 8, 17), numero_factura="AS001")
    db.session.add(compra1)
    db.session.flush()
    db.session.add(CompraDetalle(compra_id=compra1.id, producto_id=coca.id, cantidad_comprada_unidades=60, costo_linea=100000, tasa_descuento_aplicada=0.0, es_descuento=True))
    db.session.add(CompraDetalle(compra_id=compra1.id, producto_id=agua.id, cantidad_comprada_unidades=60, costo_linea=50000, tasa_descuento_aplicada=0.0, es_descuento=True))
    db.session.commit()

    compra2, _ = crear_compra_detalle(db, coca, date(2026, 8, 18), costo_linea=200000, numero_factura="AS002")

    grupos = listar_descuentos_agrupados(date(2026, 8, 1), date(2026, 8, 31))

    assert len(grupos) == 2
    assert grupos[0]["compra"].numero_factura == "AS002"
    assert grupos[0]["subtotal"] == 200000
    assert grupos[1]["compra"].numero_factura == "AS001"
    assert len(grupos[1]["lineas"]) == 2
    assert grupos[1]["subtotal"] == 150000


def test_rendimiento_por_producto_ordena_por_descuento_contabilizado(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    agua = crear_producto(db, "Agua Cristal", 3000)

    crear_compra_detalle(db, coca, date(2026, 8, 1), costo_linea=90000, es_descuento=True)
    crear_compra_detalle(db, agua, date(2026, 8, 1), costo_linea=150000, es_descuento=True)

    filas = rendimiento_por_producto(date(2026, 8, 1), date(2026, 8, 31))

    assert len(filas) == 2
    assert filas[0]["producto"] == "Agua Cristal"
    assert filas[0]["descuento_contabilizado"] == 150000
    assert filas[1]["producto"] == "Coca-Cola 1.5L"
    assert filas[1]["descuento_contabilizado"] == 90000


def test_rendimiento_por_producto_fuera_del_periodo_no_aparece(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    crear_compra_detalle(db, coca, date(2026, 5, 1), costo_linea=90000, es_descuento=True)

    assert rendimiento_por_producto(date(2026, 8, 1), date(2026, 8, 31)) == []


def test_pagina_descuentos_muestra_grupo_y_total(db, client):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, es_descuento=True)

    r = client.get("/descuentos/?anio=2026&mes=8")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Coca-Cola 1.5L" in body
    assert "AS001" in body
    assert "100,000" in body


def test_pagina_descuentos_vacia_cuando_no_hay_nada(client):
    r = client.get("/descuentos/?anio=2026&mes=8")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "No hay descuentos" in body


def test_exportar_excel_descarga_archivo(db, client):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, es_descuento=True)

    r = client.get("/descuentos/exportar-excel?anio=2026&mes=8")
    assert r.status_code == 200
    assert r.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in r.headers.get("Content-Disposition", "")
