from datetime import date

from models import (
    Producto,
    ProductoPrecio,
    Compra,
    CompraDetalle,
    SalidaCamion,
    SalidaCamionDetalle,
    RetornoCamion,
    RetornoCamionDetalle,
    CanjeDescuento,
    CanjeDescuentoDetalle,
)
from services.reportes import resumen_periodo


def crear_producto(db, nombre, precio):
    p = Producto(nombre=nombre, unidades_por_caja=6, maneja_cajas=True, maneja_unidades=True)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, vigente_desde=date(2026, 1, 1)))
    db.session.commit()
    return p


def test_caso_end_to_end_del_plan(db):
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

    salida = SalidaCamion(fecha=date(2026, 8, 2))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=30))
    db.session.commit()

    retorno = RetornoCamion(salida_id=salida.id, fecha=date(2026, 8, 2))
    db.session.add(retorno)
    db.session.flush()
    db.session.add(RetornoCamionDetalle(retorno_id=retorno.id, producto_id=coca.id, cantidad_unidades=6))
    db.session.commit()

    canje = CanjeDescuento(fecha=date(2026, 8, 5))
    db.session.add(canje)
    db.session.flush()
    db.session.add(
        CanjeDescuentoDetalle(canje_id=canje.id, producto_id=agua.id, cantidad_unidades=3, valor_usado=9000)
    )
    db.session.commit()

    resumen = resumen_periodo(date(2026, 8, 1), date(2026, 8, 31))

    assert resumen["compra_total_dinero"] == 180000
    assert resumen["compra_total_unidades"] == 60
    assert resumen["credito_generado"] == 9000
    assert resumen["credito_canjeado"] == 9000
    assert resumen["saldo_acumulado"] == 0
    assert resumen["venta_total_dinero"] == 72000
    assert resumen["pct_descuento_promedio"] == 5.0


def test_pct_descuento_promedio_pondera_por_dinero_comprado(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    hit = crear_producto(db, "Hit Mango", 1500)

    compra = Compra(fecha=date(2026, 8, 1))
    db.session.add(compra)
    db.session.flush()
    # 800,000 comprados al 10% + 200,000 comprados al 2% -> promedio ponderado, no simple
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=200,
            costo_linea=800000, tasa_descuento_aplicada=10.0,
        )
    )
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=hit.id, cantidad_comprada_unidades=100,
            costo_linea=200000, tasa_descuento_aplicada=2.0,
        )
    )
    db.session.commit()

    resumen = resumen_periodo(date(2026, 8, 1), date(2026, 8, 31))

    # credito = 80000 + 4000 = 84000; compra_total = 1,000,000 -> 8.4%, no el 6% simple
    assert resumen["credito_generado"] == 84000
    assert resumen["pct_descuento_promedio"] == 8.4


def test_pct_descuento_promedio_sin_compras_es_cero(db):
    resumen = resumen_periodo(date(2026, 8, 1), date(2026, 8, 31))
    assert resumen["pct_descuento_promedio"] == 0.0
