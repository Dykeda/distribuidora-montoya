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
    CategoriaGasto,
    Gasto,
)
from services.reportes import resumen_periodo


def crear_producto(db, nombre, precio):
    p = Producto(nombre=nombre, unidades_por_caja=6, maneja_cajas=True, maneja_unidades=True)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, precio_venta_caja=precio * 6, vigente_desde=date(2026, 1, 1)))
    db.session.commit()
    return p


def test_caso_end_to_end_del_plan(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    agua = crear_producto(db, "Agua Cristal", 3000)

    compra = Compra(fecha=date(2026, 8, 1), numero_factura="AS001")
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
            compra_id=compra.id, producto_id=agua.id, cantidad_comprada_unidades=3,
            costo_linea=9000, tasa_descuento_aplicada=0.0, es_descuento=True,
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

    resumen = resumen_periodo(date(2026, 8, 1), date(2026, 8, 31))

    assert resumen["compra_total_dinero"] == 189000
    assert resumen["compra_total_unidades"] == 63
    assert resumen["descuento_contabilizado"] == 9000
    assert resumen["venta_total_dinero"] == 72000
    assert resumen["pct_descuento_promedio"] == round(9000 / 189000 * 100, 1)


def test_descuento_contabilizado_suma_solo_lineas_marcadas(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    hit = crear_producto(db, "Hit Mango", 1500)

    compra = Compra(fecha=date(2026, 8, 1), numero_factura="AS001")
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=200,
            costo_linea=80000, tasa_descuento_aplicada=0.0, es_descuento=True,
        )
    )
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=hit.id, cantidad_comprada_unidades=100,
            costo_linea=4000, tasa_descuento_aplicada=0.0, es_descuento=True,
        )
    )
    db.session.commit()

    resumen = resumen_periodo(date(2026, 8, 1), date(2026, 8, 31))

    assert resumen["descuento_contabilizado"] == 84000


def test_pct_descuento_promedio_sin_compras_es_cero(db):
    resumen = resumen_periodo(date(2026, 8, 1), date(2026, 8, 31))
    assert resumen["pct_descuento_promedio"] == 0.0


def test_compra_total_dinero_incluye_iva_igual_que_historial_de_compras(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    agua = crear_producto(db, "Agua Cristal", 2000)

    compra = Compra(fecha=date(2026, 8, 1), numero_factura="AS001")
    db.session.add(compra)
    db.session.flush()
    db.session.add(CompraDetalle(
        compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=60,
        costo_linea=100000, tasa_descuento_aplicada=0.0, porcentaje_iva=19.0,
    ))
    db.session.add(CompraDetalle(
        compra_id=compra.id, producto_id=agua.id, cantidad_comprada_unidades=12,
        costo_linea=24000, tasa_descuento_aplicada=0.0, porcentaje_iva=0.0,
    ))
    db.session.commit()

    resumen = resumen_periodo(date(2026, 8, 1), date(2026, 8, 31))

    # 100000 + 19% IVA = 119000 ; + 24000 (sin IVA) = 143000
    assert resumen["compra_total_dinero"] == 143000
    # el % de descuento promedio sigue comparando contra el neto (sin IVA), no cambia
    assert resumen["pct_descuento_promedio"] == 0.0


def test_ganancia_neta_resta_solo_gastos_de_negocio(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    compra = Compra(fecha=date(2026, 8, 1), numero_factura="AS001")
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=60,
            costo_linea=10000, tasa_descuento_aplicada=0.0, es_descuento=True,
        )
    )
    db.session.commit()
    # descuento contabilizado = 10000

    cat_negocio = CategoriaGasto.query.filter_by(tipo="negocio").first()
    cat_hogar = CategoriaGasto.query.filter_by(tipo="hogar").first()
    db.session.add(Gasto(categoria_id=cat_negocio.id, fecha=date(2026, 8, 5), monto=4000))
    db.session.add(Gasto(categoria_id=cat_hogar.id, fecha=date(2026, 8, 5), monto=2000))
    db.session.commit()

    resumen = resumen_periodo(date(2026, 8, 1), date(2026, 8, 31))

    assert resumen["gastos_negocio_periodo"] == 4000
    # 10000 (descuento) - 4000 (gastos negocio) = 6000 -- el gasto de hogar (2000) NO cuenta
    assert resumen["ganancia_neta_periodo"] == 6000
    assert resumen["ganancia_neta_acumulada"] == 6000
