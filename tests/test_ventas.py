from datetime import date

from models import (
    Producto,
    ProductoPrecio,
    SalidaCamion,
    SalidaCamionDetalle,
    RetornoCamion,
    RetornoCamionDetalle,
)
from services.ventas import venta_por_salida, ventas_en_periodo, rutas_en_transito


def crear_producto(db, nombre="Coca-Cola 1.5L", precio=3000):
    p = Producto(nombre=nombre, unidades_por_caja=6, maneja_cajas=True, maneja_unidades=True)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, vigente_desde=date(2026, 1, 1)))
    db.session.commit()
    return p


def test_venta_implicita_salida_menos_retorno(db):
    p = crear_producto(db)
    salida = SalidaCamion(fecha=date(2026, 8, 2))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=p.id, cantidad_unidades=30))
    db.session.commit()

    retorno = RetornoCamion(salida_id=salida.id, fecha=date(2026, 8, 2))
    db.session.add(retorno)
    db.session.flush()
    db.session.add(RetornoCamionDetalle(retorno_id=retorno.id, producto_id=p.id, cantidad_unidades=6))
    db.session.commit()

    detalle = venta_por_salida(salida.id)
    assert detalle[0]["cantidad_vendida"] == 24
    assert detalle[0]["valor"] == 72000

    resumen = ventas_en_periodo(date(2026, 8, 1), date(2026, 8, 31))
    assert resumen["total"] == 72000


def test_ruta_sin_retorno_esta_en_transito_y_no_cuenta(db):
    p = crear_producto(db)
    salida = SalidaCamion(fecha=date(2026, 8, 2))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=p.id, cantidad_unidades=30))
    db.session.commit()

    assert venta_por_salida(salida.id) is None
    assert len(rutas_en_transito()) == 1

    resumen = ventas_en_periodo(date(2026, 8, 1), date(2026, 8, 31))
    assert resumen["total"] == 0
