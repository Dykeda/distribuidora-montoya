from datetime import date

import pytest

from models import (
    Producto,
    ProductoPrecio,
    Compra,
    CompraDetalle,
    CanjeDescuento,
    CanjeDescuentoDetalle,
    AjusteCredito,
)
from services.descuentos import (
    credito_generado_periodo,
    credito_canjeado_periodo,
    saldo_acumulado,
    rendimiento_por_producto,
)
from services.inventario import calcular_stock


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


def test_credito_generado_por_compra(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    compra = Compra(fecha=date(2026, 8, 1))
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=60,
            costo_linea=180000, tasa_descuento_aplicada=5.0,
        )
    )
    db.session.commit()

    assert credito_generado_periodo(date(2026, 8, 1), date(2026, 8, 31)) == 9000


def test_canje_reduce_saldo_y_sube_stock_de_otro_producto(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    agua = crear_producto(db, "Agua Cristal", 3000)

    compra = Compra(fecha=date(2026, 8, 1))
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=60,
            costo_linea=180000, tasa_descuento_aplicada=5.0,
        )
    )
    db.session.commit()

    assert saldo_acumulado(date(2026, 8, 31)) == 9000

    canje = CanjeDescuento(fecha=date(2026, 8, 5))
    db.session.add(canje)
    db.session.flush()
    db.session.add(
        CanjeDescuentoDetalle(canje_id=canje.id, producto_id=agua.id, cantidad_unidades=3, valor_usado=9000)
    )
    db.session.commit()

    assert credito_canjeado_periodo(date(2026, 8, 1), date(2026, 8, 31)) == 9000
    assert saldo_acumulado(date(2026, 8, 31)) == 0
    assert calcular_stock(agua.id) == 3


def test_ajuste_suma_al_saldo_acumulado(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    compra = Compra(fecha=date(2026, 8, 1))
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=60,
            costo_linea=180000, tasa_descuento_aplicada=5.0,
        )
    )
    db.session.add(
        AjusteCredito(fecha=date(2026, 7, 1), monto=50000, notas="Saldo acumulado antes del sistema")
    )
    db.session.commit()

    # 9000 generado por la compra + 50000 del ajuste inicial
    assert saldo_acumulado(date(2026, 8, 31)) == 59000


def test_ajuste_negativo_resta_del_saldo(db):
    db.session.add(AjusteCredito(fecha=date(2026, 7, 1), monto=50000))
    db.session.add(AjusteCredito(fecha=date(2026, 7, 15), monto=-20000, notas="Corrección"))
    db.session.commit()

    assert saldo_acumulado(date(2026, 8, 31)) == 30000


def test_rendimiento_por_producto_ordena_por_credito_generado(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    agua = crear_producto(db, "Agua Cristal", 3000)

    compra = Compra(fecha=date(2026, 8, 1))
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=60,
            costo_linea=180000, tasa_descuento_aplicada=5.0,
        )
    )
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=agua.id, cantidad_comprada_unidades=60,
            costo_linea=100000, tasa_descuento_aplicada=15.0,
        )
    )
    db.session.commit()

    filas = rendimiento_por_producto(date(2026, 8, 1), date(2026, 8, 31))

    assert len(filas) == 2
    # agua generó 15000 de crédito, coca solo 9000 -> agua primero aunque se compró menos
    assert filas[0]["producto"] == "Agua Cristal"
    assert filas[0]["credito_generado"] == 15000
    assert filas[0]["tasa_promedio"] == 15.0
    assert filas[1]["producto"] == "Coca-Cola 1.5L"
    assert filas[1]["credito_generado"] == 9000


def test_rendimiento_por_producto_fuera_del_periodo_no_aparece(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    compra = Compra(fecha=date(2026, 5, 1))
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=60,
            costo_linea=180000, tasa_descuento_aplicada=5.0,
        )
    )
    db.session.commit()

    assert rendimiento_por_producto(date(2026, 8, 1), date(2026, 8, 31)) == []


def _crear_canje_con_dos_productos(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    agua = crear_producto(db, "Agua Cristal", 2000)
    canje = CanjeDescuento(fecha=date(2026, 8, 5), notas="Canje de prueba")
    db.session.add(canje)
    db.session.flush()
    db.session.add(CanjeDescuentoDetalle(canje_id=canje.id, producto_id=coca.id, cantidad_unidades=6, valor_usado=18000))
    db.session.add(CanjeDescuentoDetalle(canje_id=canje.id, producto_id=agua.id, cantidad_unidades=3, valor_usado=6000))
    db.session.commit()
    return canje, coca, agua


def test_canje_detalle_muestra_los_productos_con_cajas_y_unidades(db, client):
    canje, coca, agua = _crear_canje_con_dos_productos(db)

    r = client.get(f"/descuentos/canje/{canje.id}")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Coca-Cola 1.5L" in body and "Agua Cristal" in body
    assert ">1<" in body  # coca: 6 unidades / 6 por caja = 1 caja


def test_editar_linea_de_canje_recalcula_valor_usado(db, client):
    canje, coca, agua = _crear_canje_con_dos_productos(db)
    detalle_coca = next(d for d in canje.detalles if d.producto_id == coca.id)

    # cambia de 6 unidades (1 caja) a 2 cajas + 1 unidad = 13 unidades
    r = client.post(
        f"/descuentos/canje/{canje.id}/linea/{detalle_coca.id}/editar",
        data={"cajas": "2", "unidades": "1"},
        follow_redirects=True,
    )
    assert r.status_code == 200

    from models import CanjeDescuentoDetalle as CDD

    actualizado = CDD.query.get(detalle_coca.id)
    assert actualizado.cantidad_unidades == 13
    assert actualizado.valor_usado == 13 * 3000
    assert calcular_stock(coca.id) == 13


def test_eliminar_linea_de_canje_deja_el_resto_intacto(db, client):
    canje, coca, agua = _crear_canje_con_dos_productos(db)
    detalle_coca = next(d for d in canje.detalles if d.producto_id == coca.id)

    r = client.post(f"/descuentos/canje/{canje.id}/linea/{detalle_coca.id}/eliminar", follow_redirects=True)
    assert r.status_code == 200

    assert CanjeDescuento.query.get(canje.id) is not None
    assert len(CanjeDescuento.query.get(canje.id).detalles) == 1
    assert calcular_stock(coca.id) == 0
    assert calcular_stock(agua.id) == 3


def test_eliminar_ultima_linea_borra_el_canje_completo(db, client):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    canje = CanjeDescuento(fecha=date(2026, 8, 5))
    db.session.add(canje)
    db.session.flush()
    db.session.add(CanjeDescuentoDetalle(canje_id=canje.id, producto_id=coca.id, cantidad_unidades=6, valor_usado=18000))
    db.session.commit()
    detalle = canje.detalles[0]

    r = client.post(f"/descuentos/canje/{canje.id}/linea/{detalle.id}/eliminar", follow_redirects=True)
    assert r.status_code == 200
    assert CanjeDescuento.query.get(canje.id) is None


def test_eliminar_canje_completo(db, client):
    canje, coca, agua = _crear_canje_con_dos_productos(db)

    r = client.post(f"/descuentos/canje/{canje.id}/eliminar", follow_redirects=True)
    assert r.status_code == 200
    assert CanjeDescuento.query.get(canje.id) is None
    assert calcular_stock(coca.id) == 0
    assert calcular_stock(agua.id) == 0
