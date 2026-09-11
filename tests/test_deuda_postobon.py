from datetime import date

import pytest

from extensions import db as _db
from models import (
    Producto, ProductoPrecio, Compra, CompraDetalle, Proveedor, CategoriaGasto, Gasto,
    AjusteDeudaPostobon,
)
from services.deuda_postobon import (
    compras_a_credito,
    pagos_transferencia,
    deuda_postobon_a_la_fecha,
    movimientos_deuda,
    listar_ajustes_deuda,
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


def test_ajuste_negativo_deja_la_deuda_en_el_valor_real(db):
    """La suma automática de facturas a crédito queda alta; un ajuste negativo la baja
    al saldo real que se debe de verdad."""
    coca = crear_producto(db)
    crear_compra_postobon(db, coca, date(2026, 9, 1), costo=500000, iva=0.0)
    assert deuda_postobon_a_la_fecha(date(2026, 9, 30)) == 500000

    db.session.add(AjusteDeudaPostobon(fecha=date(2026, 9, 8), monto=-380000, notas="Saldo real"))
    db.session.commit()

    assert deuda_postobon_a_la_fecha(date(2026, 9, 30)) == 120000


def test_ajuste_positivo_suma_a_la_deuda(db):
    db.session.add(AjusteDeudaPostobon(fecha=date(2026, 9, 1), monto=250000, notas="Deuda vieja"))
    db.session.commit()

    assert deuda_postobon_a_la_fecha(date(2026, 9, 30)) == 250000


def test_ajuste_solo_cuenta_hasta_su_fecha(db):
    db.session.add(AjusteDeudaPostobon(fecha=date(2026, 9, 20), monto=-100000))
    db.session.commit()

    assert deuda_postobon_a_la_fecha(date(2026, 9, 10)) == 0
    assert deuda_postobon_a_la_fecha(date(2026, 9, 30)) == -100000


def test_ajuste_aparece_en_movimientos_con_saldo_corrido(db):
    coca = crear_producto(db)
    crear_compra_postobon(db, coca, date(2026, 9, 1), costo=100000, iva=0.0, numero_factura="AS001")
    db.session.add(AjusteDeudaPostobon(fecha=date(2026, 9, 15), monto=-30000, notas="Ajuste"))
    db.session.commit()

    movimientos = movimientos_deuda(date(2026, 9, 1), date(2026, 9, 30))
    assert len(movimientos) == 2
    assert movimientos[0]["tipo"] == "ajuste"
    assert movimientos[0]["monto"] == -30000
    assert movimientos[0]["saldo"] == 70000
    assert movimientos[1]["tipo"] == "cargo"
    assert movimientos[1]["saldo"] == 100000


def test_ajuste_oculto_suma_a_la_deuda_pero_no_aparece_en_movimientos(db):
    coca = crear_producto(db)
    crear_compra_postobon(db, coca, date(2026, 9, 1), costo=100000, iva=0.0, numero_factura="AS001")
    db.session.add(AjusteDeudaPostobon(
        fecha=date(2026, 8, 31), monto=-30000, notas="Base limpia", oculto=True,
    ))
    db.session.commit()

    assert deuda_postobon_a_la_fecha(date(2026, 9, 30)) == 70000

    movimientos = movimientos_deuda(date(2026, 9, 1), date(2026, 9, 30))
    assert len(movimientos) == 1
    assert movimientos[0]["tipo"] == "cargo"
    assert movimientos[0]["saldo"] == 70000


def test_listar_ajustes_deuda_omite_los_ocultos(db):
    db.session.add(AjusteDeudaPostobon(fecha=date(2026, 9, 1), monto=-30000, oculto=True))
    db.session.add(AjusteDeudaPostobon(fecha=date(2026, 9, 2), monto=10000, oculto=False))
    db.session.commit()

    visibles = listar_ajustes_deuda()
    assert len(visibles) == 1
    assert visibles[0].monto == 10000


def test_form_crea_ajuste_de_deuda(db, client):
    r = client.post(
        "/deuda-postobon/ajustes/nuevo",
        data={"fecha": "2026-09-08", "monto": "-380000", "notas": "Saldo real"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    ajuste = AjusteDeudaPostobon.query.one()
    assert ajuste.monto == -380000
    assert ajuste.notas == "Saldo real"


def test_form_rechaza_ajuste_en_cero(db, client):
    r = client.post(
        "/deuda-postobon/ajustes/nuevo",
        data={"fecha": "2026-09-08", "monto": "0", "notas": ""},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert AjusteDeudaPostobon.query.count() == 0
    assert "no puede ser cero" in r.get_data(as_text=True)


def test_eliminar_ajuste_de_deuda(db, client):
    db.session.add(AjusteDeudaPostobon(fecha=date(2026, 9, 8), monto=-380000))
    db.session.commit()
    ajuste_id = AjusteDeudaPostobon.query.one().id

    r = client.post(
        f"/deuda-postobon/ajustes/{ajuste_id}/eliminar", follow_redirects=True,
    )
    assert r.status_code == 200
    assert AjusteDeudaPostobon.query.count() == 0
    assert listar_ajustes_deuda() == []
