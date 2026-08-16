from datetime import date

from models import Producto, ProductoPrecio, Compra, CompraDetalle, SalidaCamion, SalidaCamionDetalle
from services.inventario import calcular_stock, cajas_y_unidades, listar_stock_todos


def crear_producto(db, nombre="Coca-Cola 1.5L", precio=3000, unidades_por_caja=6):
    p = Producto(nombre=nombre, unidades_por_caja=unidades_por_caja, maneja_cajas=True, maneja_unidades=True)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, precio_venta_caja=precio * unidades_por_caja, vigente_desde=date(2026, 1, 1)))
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


def test_cajas_y_unidades_divide_normal_si_el_producto_maneja_cajas(db):
    p = crear_producto(db, unidades_por_caja=6)
    assert cajas_y_unidades(p, 15) == (2, 3)


def test_cajas_y_unidades_todo_como_unidades_sueltas_si_no_maneja_cajas(db):
    # ej. bolsas de agua sueltas: unidades_por_caja=1 no significa que se empaquen en
    # "cajas" de 1 -- sin maneja_cajas, el stock entero debe verse como unidades sueltas.
    p = Producto(nombre="Agua Bolsa 6 Lts", unidades_por_caja=1, maneja_cajas=False, maneja_unidades=True)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=1000, precio_venta_caja=1000, vigente_desde=date(2026, 1, 1)))
    db.session.commit()

    assert cajas_y_unidades(p, 8) == (0, 8)

    compra = Compra(fecha=date(2026, 8, 1))
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(compra_id=compra.id, producto_id=p.id, cantidad_comprada_unidades=8, costo_linea=8000, tasa_descuento_aplicada=0.0)
    )
    db.session.commit()

    fila = next(f for f in listar_stock_todos() if f["producto"].id == p.id)
    assert fila["cajas"] == 0
    assert fila["unidades_sueltas"] == 8
