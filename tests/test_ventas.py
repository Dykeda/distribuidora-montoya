from datetime import date

from models import (
    Producto,
    ProductoPrecio,
    SalidaCamion,
    SalidaCamionDetalle,
    RetornoCamion,
    RetornoCamionDetalle,
    RecargaCamion,
    RecargaCamionDetalle,
    VentaBodega,
    VentaBodegaDetalle,
)
from services.ventas import (
    venta_por_salida,
    ventas_en_periodo,
    rutas_en_transito,
    historial_diario,
    detalle_dia,
)
from services.inventario import calcular_stock


def crear_producto(db, nombre="Coca-Cola 1.5L", precio=3000):
    p = Producto(nombre=nombre, unidades_por_caja=6, maneja_cajas=True, maneja_unidades=True)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, precio_venta_caja=precio * 6, vigente_desde=date(2026, 1, 1)))
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


def test_recarga_se_suma_a_lo_cargado_de_la_ruta(db):
    p = crear_producto(db)
    salida = SalidaCamion(fecha=date(2026, 8, 2))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=p.id, cantidad_unidades=30))
    db.session.commit()

    assert calcular_stock(p.id) == -30  # sin compra previa en este test, solo interesa el movimiento

    recarga = RecargaCamion(salida_id=salida.id, fecha=date(2026, 8, 2))
    db.session.add(recarga)
    db.session.flush()
    db.session.add(RecargaCamionDetalle(recarga_id=recarga.id, producto_id=p.id, cantidad_unidades=12))
    db.session.commit()

    assert calcular_stock(p.id) == -42  # 30 de la salida + 12 de la recarga

    retorno = RetornoCamion(salida_id=salida.id, fecha=date(2026, 8, 2))
    db.session.add(retorno)
    db.session.flush()
    db.session.add(RetornoCamionDetalle(retorno_id=retorno.id, producto_id=p.id, cantidad_unidades=6))
    db.session.commit()

    detalle = venta_por_salida(salida.id)
    # cargado = 30 (salida) + 12 (recarga) = 42; regresó 6 -> vendido = 36
    assert detalle[0]["cantidad_vendida"] == 36
    assert detalle[0]["valor"] == 36 * 3000


def test_venta_bodega_descuenta_stock_y_suma_a_venta_del_periodo(db):
    p = crear_producto(db)

    venta = VentaBodega(fecha=date(2026, 8, 3))
    db.session.add(venta)
    db.session.flush()
    db.session.add(
        VentaBodegaDetalle(venta_id=venta.id, producto_id=p.id, cantidad_unidades=10, valor=30000)
    )
    db.session.commit()

    assert calcular_stock(p.id) == -10

    resumen = ventas_en_periodo(date(2026, 8, 1), date(2026, 8, 31))
    assert resumen["total"] == 30000
    assert resumen["por_producto"]["Coca-Cola 1.5L"] == 30000


def test_historial_diario_no_resta_cartera(db):
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

    from models import FacturaCartera

    # 20000 de esos 72000 quedaron en cartera -> el efectivo de Caja sería 52000, pero
    # la venta bruta del día debe seguir mostrando los 72000 completos
    db.session.add(
        FacturaCartera(salida_id=salida.id, cliente="Tienda X", fecha=date(2026, 8, 2), monto=20000)
    )
    db.session.commit()

    venta_bodega = VentaBodega(fecha=date(2026, 8, 2))
    db.session.add(venta_bodega)
    db.session.flush()
    db.session.add(VentaBodegaDetalle(venta_id=venta_bodega.id, producto_id=p.id, cantidad_unidades=5, valor=15000))
    db.session.commit()

    filas = historial_diario(date(2026, 8, 1), date(2026, 8, 31))
    assert len(filas) == 1
    assert filas[0]["fecha"] == date(2026, 8, 2)
    assert filas[0]["camion"] == 72000
    assert filas[0]["bodega"] == 15000
    assert filas[0]["total"] == 87000


def test_detalle_dia_incluye_rutas_y_ventas_bodega(db):
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

    venta_bodega = VentaBodega(fecha=date(2026, 8, 2))
    db.session.add(venta_bodega)
    db.session.flush()
    db.session.add(VentaBodegaDetalle(venta_id=venta_bodega.id, producto_id=p.id, cantidad_unidades=5, valor=15000))
    db.session.commit()

    detalle = detalle_dia(date(2026, 8, 2))
    assert len(detalle["rutas"]) == 1
    assert detalle["rutas"][0]["total"] == 72000
    assert len(detalle["ventas_bodega"]) == 1
    assert detalle["ventas_bodega"][0]["total"] == 15000

    assert detalle_dia(date(2026, 8, 5)) == {"rutas": [], "ventas_bodega": []}
