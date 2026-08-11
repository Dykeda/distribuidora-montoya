from datetime import date

from models import (
    Producto,
    ProductoPrecio,
    Compra,
    CompraDetalle,
    CanjeDescuento,
    CanjeDescuentoDetalle,
    AjusteCredito,
)
from services.descuentos import credito_generado_periodo, credito_canjeado_periodo, saldo_acumulado
from services.inventario import calcular_stock


def crear_producto(db, nombre, precio):
    p = Producto(nombre=nombre, unidades_por_caja=6, maneja_cajas=True, maneja_unidades=True)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, vigente_desde=date(2026, 1, 1)))
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
