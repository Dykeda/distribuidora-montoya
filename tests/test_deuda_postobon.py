from datetime import date

import pytest

from extensions import db as _db
from models import Producto, ProductoPrecio, Compra, CompraDetalle, Proveedor, CategoriaGasto, Gasto
from services.deuda_postobon import (
    compras_a_credito,
    pagos_transferencia,
    deuda_postobon_a_la_fecha,
    movimientos_deuda,
)


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


def crear_compra_postobon(db, producto, fecha, costo=100000, iva=19.0, pago_contado=False, numero_factura=None):
    compra = Compra(fecha=fecha, pago_contado=pago_contado, numero_factura=numero_factura)
    db.session.add(compra)
    db.session.flush()
    db.session.add(CompraDetalle(
        compra_id=compra.id, producto_id=producto.id, cantidad_comprada_unidades=6,
        costo_linea=costo, tasa_descuento_aplicada=10.0, porcentaje_iva=iva,
    ))
    db.session.commit()
    return compra


def crear_pago_transferencia(db, fecha, monto):
    categoria = CategoriaGasto.query.filter_by(nombre="Pago Postobón Transferencia").first()
    gasto = Gasto(categoria_id=categoria.id, fecha=fecha, monto=monto)
    db.session.add(gasto)
    db.session.commit()
    return gasto


def test_compra_a_credito_suma_a_la_deuda(db):
    coca = crear_producto(db)
    crear_compra_postobon(db, coca, date(2026, 9, 1), costo=100000, iva=19.0)

    deuda = deuda_postobon_a_la_fecha(date(2026, 9, 30))
    assert deuda == 119000  # 100000 neto + 19% IVA


def test_compra_pago_de_contado_no_suma_a_la_deuda(db):
    coca = crear_producto(db)
    crear_compra_postobon(db, coca, date(2026, 9, 1), costo=100000, iva=19.0, pago_contado=True)

    assert deuda_postobon_a_la_fecha(date(2026, 9, 30)) == 0
    assert compras_a_credito(None, date(2026, 9, 30)) == []


def test_pago_por_transferencia_resta_de_la_deuda(db):
    coca = crear_producto(db)
    crear_compra_postobon(db, coca, date(2026, 9, 1), costo=100000, iva=0.0)
    crear_pago_transferencia(db, date(2026, 9, 5), 60000)

    assert deuda_postobon_a_la_fecha(date(2026, 9, 30)) == 40000


def test_pago_de_contado_no_es_transferencia_y_no_afecta_la_deuda(db):
    """La categoría "Pago Postobón Contado" es un gasto distinto -- no debe restar de la
    deuda, porque la compra de contado nunca la sumó."""
    categoria_contado = CategoriaGasto.query.filter_by(nombre="Pago Postobón Contado").first()
    db.session.add(Gasto(categoria_id=categoria_contado.id, fecha=date(2026, 9, 5), monto=50000))
    db.session.commit()

    assert deuda_postobon_a_la_fecha(date(2026, 9, 30)) == 0


def test_compra_de_proveedor_no_postobon_no_afecta_la_deuda(db):
    coca = crear_producto(db)
    externo = Proveedor(nombre="Canasto", es_postobon=False)
    db.session.add(externo)
    db.session.flush()
    compra = Compra(fecha=date(2026, 9, 1), proveedor_id=externo.id)
    db.session.add(compra)
    db.session.flush()
    db.session.add(CompraDetalle(
        compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=6,
        costo_linea=100000, tasa_descuento_aplicada=0.0, porcentaje_iva=0.0,
    ))
    db.session.commit()

    assert deuda_postobon_a_la_fecha(date(2026, 9, 30)) == 0


def test_movimientos_deuda_incluye_saldo_corrido(db):
    coca = crear_producto(db)
    crear_compra_postobon(db, coca, date(2026, 9, 1), costo=100000, iva=0.0, numero_factura="AS001")
    crear_pago_transferencia(db, date(2026, 9, 10), 40000)

    movimientos = movimientos_deuda(date(2026, 9, 1), date(2026, 9, 30))
    assert len(movimientos) == 2
    # ordenados más reciente primero
    assert movimientos[0]["tipo"] == "abono"
    assert movimientos[0]["saldo"] == 60000
    assert movimientos[1]["tipo"] == "cargo"
    assert movimientos[1]["saldo"] == 100000


def test_pagina_deuda_postobon_responde(client, db):
    r = client.get("/deuda-postobon/")
    assert r.status_code == 200
    assert "Deuda pendiente con Postob" in r.get_data(as_text=True)


def test_nueva_compra_marca_pago_contado(db, client):
    coca = crear_producto(db)

    r = client.post(
        "/compras/nueva",
        data={
            "fecha": "2026-09-08", "numero_factura": "", "notas": "", "pago_contado": "1",
            "producto_id[]": [str(coca.id)], "cajas[]": ["1"], "unidades[]": ["0"],
            "costo_linea[]": ["18000"], "tasa_descuento[]": ["0"],
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert Compra.query.one().pago_contado is True


def test_nueva_compra_sin_marcar_queda_a_credito(db, client):
    coca = crear_producto(db)

    r = client.post(
        "/compras/nueva",
        data={
            "fecha": "2026-09-08", "numero_factura": "", "notas": "",
            "producto_id[]": [str(coca.id)], "cajas[]": ["1"], "unidades[]": ["0"],
            "costo_linea[]": ["18000"], "tasa_descuento[]": ["0"],
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert Compra.query.one().pago_contado is False
