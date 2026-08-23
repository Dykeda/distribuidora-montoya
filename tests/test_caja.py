from datetime import date

from models import (
    Producto,
    ProductoPrecio,
    SalidaCamion,
    SalidaCamionDetalle,
    RetornoCamion,
    RetornoCamionDetalle,
    FacturaCartera,
    Cliente,
    VentaBodega,
    VentaBodegaDetalle,
    CategoriaGasto,
    Gasto,
)
from services.caja import (
    efectivo_por_salida,
    entradas_en_periodo,
    historial_diario,
    saldo_acumulado,
    saldo_en_periodo,
)


def crear_producto(db, nombre="Coca-Cola 1.5L", precio=3000, unidades_por_caja=6):
    p = Producto(nombre=nombre, unidades_por_caja=unidades_por_caja, maneja_cajas=True, maneja_unidades=True)
    db.session.add(p)
    db.session.flush()
    db.session.add(
        ProductoPrecio(
            producto_id=p.id, precio_venta_unidad=precio, precio_venta_caja=precio * unidades_por_caja,
            vigente_desde=date(2026, 1, 1),
        )
    )
    db.session.commit()
    return p


def cerrar_ruta(db, producto, cantidad_salida, cantidad_retorno, fecha=date(2026, 8, 2)):
    salida = SalidaCamion(fecha=fecha)
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=producto.id, cantidad_unidades=cantidad_salida))
    db.session.commit()

    retorno = RetornoCamion(salida_id=salida.id, fecha=fecha)
    db.session.add(retorno)
    db.session.flush()
    db.session.add(RetornoCamionDetalle(retorno_id=retorno.id, producto_id=producto.id, cantidad_unidades=cantidad_retorno))
    db.session.commit()
    return salida


def test_efectivo_por_salida_sin_cartera_es_toda_la_venta(db):
    p = crear_producto(db)
    salida = cerrar_ruta(db, p, cantidad_salida=30, cantidad_retorno=6)

    # vendido = 24 unidades x 3000 = 72000, sin cartera -> todo es efectivo
    assert efectivo_por_salida(salida.id) == 72000


def test_efectivo_por_salida_resta_lo_que_quedo_en_cartera(db):
    p = crear_producto(db)
    salida = cerrar_ruta(db, p, cantidad_salida=30, cantidad_retorno=6)

    ahorro = Cliente(nombre="Tienda El Ahorro")
    db.session.add(ahorro)
    db.session.flush()
    db.session.add(
        FacturaCartera(salida_id=salida.id, cliente_id=ahorro.id, fecha=date(2026, 8, 2), monto=20000)
    )
    db.session.commit()

    # 72000 de venta - 20000 que quedó a deber = 52000 en efectivo
    assert efectivo_por_salida(salida.id) == 52000


def test_entradas_en_periodo_suma_camion_y_bodega(db):
    p = crear_producto(db)
    cerrar_ruta(db, p, cantidad_salida=30, cantidad_retorno=6, fecha=date(2026, 8, 2))  # 72000 efectivo

    venta_bodega = VentaBodega(fecha=date(2026, 8, 3))
    db.session.add(venta_bodega)
    db.session.flush()
    db.session.add(VentaBodegaDetalle(venta_id=venta_bodega.id, producto_id=p.id, cantidad_unidades=5, valor=15000))
    db.session.commit()

    assert entradas_en_periodo(date(2026, 8, 1), date(2026, 8, 31)) == 72000 + 15000


def test_saldo_en_periodo_resta_los_gastos(db):
    p = crear_producto(db)
    cerrar_ruta(db, p, cantidad_salida=30, cantidad_retorno=6, fecha=date(2026, 8, 2))  # 72000 entrada

    cat = CategoriaGasto.query.filter_by(nombre="Arriendo", tipo="hogar").first()
    db.session.add(Gasto(categoria_id=cat.id, fecha=date(2026, 8, 10), monto=30000))
    db.session.commit()

    assert saldo_en_periodo(date(2026, 8, 1), date(2026, 8, 31)) == 72000 - 30000


def test_historial_diario_separa_por_fecha_y_fuente(db):
    p = crear_producto(db)
    cerrar_ruta(db, p, cantidad_salida=30, cantidad_retorno=6, fecha=date(2026, 8, 2))

    venta_bodega = VentaBodega(fecha=date(2026, 8, 2))
    db.session.add(venta_bodega)
    db.session.flush()
    db.session.add(VentaBodegaDetalle(venta_id=venta_bodega.id, producto_id=p.id, cantidad_unidades=5, valor=15000))
    db.session.commit()

    cat = CategoriaGasto.query.filter_by(nombre="Pago Nómina", tipo="negocio").first()
    db.session.add(Gasto(categoria_id=cat.id, fecha=date(2026, 8, 2), monto=10000))
    db.session.commit()

    filas = historial_diario(date(2026, 8, 1), date(2026, 8, 31))
    assert len(filas) == 1
    assert filas[0]["fecha"] == date(2026, 8, 2)
    assert filas[0]["camion"] == 72000
    assert filas[0]["bodega"] == 15000
    assert filas[0]["gastos"] == 10000
    assert filas[0]["total"] == 72000 + 15000 - 10000


def test_saldo_acumulado_no_tiene_limite_inferior_y_resta_gastos(db):
    # el precio del producto rige desde 2026-01-01; la ruta es de esa misma semana, muy
    # anterior a la fecha de corte usada abajo, para probar que no hay límite inferior
    p = crear_producto(db)
    cerrar_ruta(db, p, cantidad_salida=30, cantidad_retorno=6, fecha=date(2026, 1, 5))

    cat = CategoriaGasto.query.filter_by(nombre="Servicios públicos", tipo="hogar").first()
    db.session.add(Gasto(categoria_id=cat.id, fecha=date(2026, 6, 1), monto=8000))
    db.session.commit()

    assert saldo_acumulado(date(2026, 12, 31)) == 72000 - 8000
