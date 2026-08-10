from datetime import date

from models import Producto, ProductoPrecio, Compra, CompraDetalle, SalidaCamion, SalidaCamionDetalle
from services.inventario import calcular_stock


def crear_producto(db, nombre="Coca-Cola 1.5L", precio=3000, unidades_por_caja=6):
    p = Producto(nombre=nombre, unidades_por_caja=unidades_por_caja, maneja_cajas=True, maneja_unidades=True)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, vigente_desde=date(2026, 1, 1)))
    db.session.commit()
    return p


def test_stock_sube_con_compra(db):
    p = crear_producto(db)
    compra = Compra(fecha=date(2026, 8, 1))
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(
            compra_id=compra.id,
            producto_id=p.id,
            cantidad_comprada_unidades=60,
            costo_linea=180000,
            tasa_descuento_aplicada=5.0,
        )
    )
    db.session.commit()

    assert calcular_stock(p.id) == 60


def test_stock_baja_con_salida(db):
    p = crear_producto(db)
    compra = Compra(fecha=date(2026, 8, 1))
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=p.id, cantidad_comprada_unidades=60,
            costo_linea=180000, tasa_descuento_aplicada=5.0,
        )
    )
    salida = SalidaCamion(fecha=date(2026, 8, 2))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=p.id, cantidad_unidades=30))
    db.session.commit()

    assert calcular_stock(p.id) == 30
