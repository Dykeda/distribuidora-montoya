from datetime import date

import pytest

from models import (
    Producto, ProductoPrecio, Compra, CompraDetalle, AjustePostobon, Proveedor,
    PagoFaltantePostobon, PagoFaltantePostobonDetalle,
)
from services.postobon import listar_faltantes, listar_faltantes_agrupados, total_pendiente_acumulado
from services.inventario import calcular_stock


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"password": app.config["APP_PASSWORD"]})
    return c


def crear_producto(db, nombre="Coca-Cola 1.5L", precio=3000, tasa_referencia=10.0):
    p = Producto(nombre=nombre, unidades_por_caja=6, maneja_cajas=True, maneja_unidades=True, tasa_descuento_referencia=tasa_referencia)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, precio_venta_caja=precio * 6, vigente_desde=date(2026, 1, 1)))
    db.session.commit()
    return p


def crear_compra_detalle(db, producto, fecha, costo_linea, tasa_aplicada, cantidad=60, numero_factura="F-001", es_descuento=False, proveedor=None):
    compra = Compra(fecha=fecha, numero_factura=numero_factura)
    if proveedor is not None:
        compra.proveedor = proveedor
    db.session.add(compra)
    db.session.flush()
    detalle = CompraDetalle(
        compra_id=compra.id, producto_id=producto.id, cantidad_comprada_unidades=cantidad,
        costo_linea=costo_linea, tasa_descuento_aplicada=tasa_aplicada, es_descuento=es_descuento,
    )
    db.session.add(detalle)
    db.session.commit()
    return compra, detalle


def crear_proveedor_externo(db, nombre="Distribuidora XYZ"):
    p = Proveedor(nombre=nombre, es_postobon=False)
    db.session.add(p)
    db.session.commit()
    return p


def test_listar_faltantes_ignora_lineas_marcadas_como_descuento(db):
    # una linea marcada "es_descuento" con 0% no es un error de Postobon, es la parte
    # de descuento en producto de la factura -- no debe verse como faltante
    coca = crear_producto(db, tasa_referencia=15.0)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=0.0, es_descuento=True)

    assert listar_faltantes(date(2026, 8, 1), date(2026, 8, 31)) == []


def test_listar_faltantes_ignora_compras_de_proveedores_distintos_a_postobon(db):
    # otro proveedor le dio un descuento menor a proposito (su propio acuerdo) -- no es un
    # faltante de Postobon, tasa_descuento_referencia solo aplica a lo que promete Postobon
    coca = crear_producto(db, tasa_referencia=15.0)
    externo = crear_proveedor_externo(db)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=5.0, proveedor=externo)

    assert listar_faltantes(date(2026, 8, 1), date(2026, 8, 31)) == []


def test_listar_faltantes_agrupados_solo_incluye_compras_de_postobon(db):
    coca = crear_producto(db, tasa_referencia=15.0)
    externo = crear_proveedor_externo(db)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=5.0, proveedor=externo, numero_factura="EXT-001")
    crear_compra_detalle(db, coca, date(2026, 8, 18), costo_linea=100000, tasa_aplicada=5.0, numero_factura="AS002")

    grupos = listar_faltantes_agrupados(date(2026, 8, 1), date(2026, 8, 31))

    assert len(grupos) == 1
    assert grupos[0]["compra"].numero_factura == "AS002"


def test_listar_faltantes_detecta_tasa_aplicada_menor_a_la_esperada(db):
    coca = crear_producto(db, tasa_referencia=15.0)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0)

    filas = listar_faltantes(date(2026, 8, 1), date(2026, 8, 31))

    assert len(filas) == 1
    assert filas[0]["producto"] == coca
    assert filas[0]["tasa_esperada"] == 15.0
    assert filas[0]["tasa_aplicada"] == 10.0
    assert filas[0]["diferencia_pct"] == 5.0
    assert filas[0]["monto_faltante"] == 5000  # 100000 * 5% = 5000


def test_listar_faltantes_no_marca_cuando_aplico_la_tasa_esperada(db):
    coca = crear_producto(db, tasa_referencia=10.0)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0)

    assert listar_faltantes(date(2026, 8, 1), date(2026, 8, 31)) == []


def test_listar_faltantes_no_marca_cuando_aplico_mas_de_lo_esperado(db):
    coca = crear_producto(db, tasa_referencia=10.0)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=20.0)

    assert listar_faltantes(date(2026, 8, 1), date(2026, 8, 31)) == []


def test_listar_faltantes_ignora_fuera_del_periodo(db):
    coca = crear_producto(db, tasa_referencia=15.0)
    crear_compra_detalle(db, coca, date(2026, 5, 1), costo_linea=100000, tasa_aplicada=5.0)

    assert listar_faltantes(date(2026, 8, 1), date(2026, 8, 31)) == []


def test_listar_faltantes_ignora_compra_sin_numero_de_factura(db):
    # ej. carga de inventario físico de bodega, no una factura real de Postobón
    coca = crear_producto(db, tasa_referencia=15.0)
    crear_compra_detalle(db, coca, date(2026, 8, 16), costo_linea=100000, tasa_aplicada=0.0, numero_factura=None)

    assert listar_faltantes(date(2026, 8, 1), date(2026, 8, 31)) == []


def test_listar_faltantes_agrupados_agrupa_por_factura_con_subtotal(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", tasa_referencia=15.0)
    agua = crear_producto(db, "Agua Cristal", tasa_referencia=10.0)

    compra1 = Compra(fecha=date(2026, 8, 17), numero_factura="AS001")
    db.session.add(compra1)
    db.session.flush()
    db.session.add(CompraDetalle(compra_id=compra1.id, producto_id=coca.id, cantidad_comprada_unidades=60, costo_linea=100000, tasa_descuento_aplicada=10.0))
    db.session.add(CompraDetalle(compra_id=compra1.id, producto_id=agua.id, cantidad_comprada_unidades=60, costo_linea=50000, tasa_descuento_aplicada=5.0))
    db.session.commit()

    compra2, _ = crear_compra_detalle(db, coca, date(2026, 8, 18), costo_linea=200000, tasa_aplicada=5.0, numero_factura="AS002")

    grupos = listar_faltantes_agrupados(date(2026, 8, 1), date(2026, 8, 31))

    assert len(grupos) == 2
    # ordenado por fecha descendente -> AS002 primero
    assert grupos[0]["compra"].numero_factura == "AS002"
    assert grupos[0]["subtotal"] == 20000  # 200000 * 10%
    assert grupos[1]["compra"].numero_factura == "AS001"
    assert len(grupos[1]["lineas"]) == 2
    assert grupos[1]["subtotal"] == 5000 + 2500  # coca: 100000*5%, agua: 50000*5%


def test_pagina_informe_muestra_faltante_agrupado_y_total(db, client):
    coca = crear_producto(db, tasa_referencia=15.0)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0, numero_factura="AS07196376")

    r = client.get("/postobon/?anio=2026&mes=8")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Coca-Cola 1.5L" in body
    assert "AS07196376" in body
    assert "5,000" in body  # monto faltante


def test_pagina_informe_vacia_cuando_no_hay_faltantes(client):
    r = client.get("/postobon/?anio=2026&mes=8")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "No hay faltantes" in body


def test_exportar_excel_descarga_archivo(db, client):
    coca = crear_producto(db, tasa_referencia=15.0)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0)

    r = client.get("/postobon/exportar-excel?anio=2026&mes=8")
    assert r.status_code == 200
    assert r.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in r.headers.get("Content-Disposition", "")


def test_exportar_excel_de_una_factura_descarga_archivo(db, client):
    coca = crear_producto(db, tasa_referencia=15.0)
    compra, _ = crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0, numero_factura="AS07196376")

    r = client.get(f"/postobon/exportar-excel/{compra.id}")
    assert r.status_code == 200
    assert r.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in r.headers.get("Content-Disposition", "")
    assert "AS07196376" in r.headers.get("Content-Disposition", "")


def test_informe_muestra_boton_de_excel_por_factura(db, client):
    coca = crear_producto(db, tasa_referencia=15.0)
    compra, _ = crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0, numero_factura="AS07196376")

    r = client.get("/postobon/?anio=2026&mes=8")
    body = r.get_data(as_text=True)
    assert f"/postobon/exportar-excel/{compra.id}" in body


def test_detalle_de_compra_resalta_fila_con_faltante(db, client):
    coca = crear_producto(db, tasa_referencia=15.0)
    compra, _ = crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0)

    r = client.get(f"/compras/{compra.id}")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "table-danger" in body
    assert "esperado 15.0%" in body


def test_detalle_de_compra_no_resalta_fila_sin_faltante(db, client):
    coca = crear_producto(db, tasa_referencia=10.0)
    compra, _ = crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0)

    r = client.get(f"/compras/{compra.id}")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "table-danger" not in body


def test_detalle_de_compra_no_resalta_fila_de_otro_proveedor_aunque_tenga_diferencia(db, client):
    # el descuento aplicado (5%) es menor que la tasa de referencia del producto (15%,
    # la que promete Postobon), pero como esta compra es de otro proveedor con su propio
    # acuerdo, no debe verse como "faltante" en el detalle de la compra
    coca = crear_producto(db, tasa_referencia=15.0)
    externo = crear_proveedor_externo(db)
    compra, _ = crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=5.0, proveedor=externo)

    r = client.get(f"/compras/{compra.id}")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "table-danger" not in body
    assert "Distribuidora XYZ" in body


def test_total_pendiente_acumulado_suma_faltantes_historicos_sin_ajustes(db):
    coca = crear_producto(db, tasa_referencia=15.0)
    crear_compra_detalle(db, coca, date(2026, 5, 1), costo_linea=100000, tasa_aplicada=10.0)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0, numero_factura="F-002")

    assert total_pendiente_acumulado(date(2026, 8, 31)) == 5000 + 5000


def test_total_pendiente_acumulado_suma_ajustes_positivos_y_negativos(db):
    coca = crear_producto(db, tasa_referencia=15.0)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0)
    db.session.add(AjustePostobon(fecha=date(2026, 1, 1), monto=200000, notas="Deuda anterior"))
    db.session.add(AjustePostobon(fecha=date(2026, 8, 20), monto=-50000, notas="Abono de Postobon"))
    db.session.commit()

    assert total_pendiente_acumulado(date(2026, 8, 31)) == 5000 + 200000 - 50000


def test_total_pendiente_acumulado_ignora_ajustes_despues_de_la_fecha_de_corte(db):
    db.session.add(AjustePostobon(fecha=date(2026, 9, 1), monto=100000))
    db.session.commit()

    assert total_pendiente_acumulado(date(2026, 8, 31)) == 0


def test_agregar_ajuste_lo_muestra_en_el_informe(db, client):
    r = client.post(
        "/postobon/ajustes/nuevo",
        data={"fecha": "2026-01-01", "monto": "150000", "notas": "Saldo pendiente anterior a esta pantalla"},
        follow_redirects=True,
    )
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Saldo pendiente anterior a esta pantalla" in body
    assert "150,000" in body

    ajuste = AjustePostobon.query.one()
    assert ajuste.monto == 150000


def test_eliminar_ajuste_lo_quita_del_informe(db, client):
    ajuste = AjustePostobon(fecha=date(2026, 1, 1), monto=150000, notas="Prueba")
    db.session.add(ajuste)
    db.session.commit()

    r = client.post(f"/postobon/ajustes/{ajuste.id}/eliminar", follow_redirects=True)
    assert r.status_code == 200
    assert AjustePostobon.query.count() == 0


def test_total_pendiente_acumulado_resta_pagos_de_faltante_en_producto(db):
    coca = crear_producto(db, tasa_referencia=15.0)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0)

    pago = PagoFaltantePostobon(fecha=date(2026, 8, 20), notas="Camión de reposición")
    pago.detalles = [PagoFaltantePostobonDetalle(producto_id=coca.id, cantidad_unidades=12, valor=2000)]
    db.session.add(pago)
    db.session.commit()

    assert total_pendiente_acumulado(date(2026, 8, 31)) == 5000 - 2000


def test_total_pendiente_acumulado_ignora_pagos_despues_de_la_fecha_de_corte(db):
    coca = crear_producto(db)
    pago = PagoFaltantePostobon(fecha=date(2026, 9, 1))
    pago.detalles = [PagoFaltantePostobonDetalle(producto_id=coca.id, cantidad_unidades=12, valor=2000)]
    db.session.add(pago)
    db.session.commit()

    assert total_pendiente_acumulado(date(2026, 8, 31)) == 0


def test_registrar_pago_de_faltante_suma_inventario_y_resta_pendiente(db, client):
    coca = crear_producto(db, tasa_referencia=15.0)
    crear_compra_detalle(db, coca, date(2026, 8, 17), costo_linea=100000, tasa_aplicada=10.0)
    stock_antes = calcular_stock(coca.id)

    r = client.post(
        "/postobon/pagos/nuevo",
        data={
            "fecha": "2026-08-20", "notas": "Camión de reposición",
            "producto_id[]": [str(coca.id)], "cajas[]": ["2"], "unidades[]": ["0"],
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Camión de reposición" in body

    pago = PagoFaltantePostobon.query.one()
    assert pago.notas == "Camión de reposición"
    detalle = pago.detalles[0]
    assert detalle.cantidad_unidades == 12  # 2 cajas * 6 unidades/caja
    assert detalle.valor == 12 * 3000  # cantidad * precio_actual()
    assert pago.valor_total == 36000

    assert calcular_stock(coca.id) == stock_antes + 12
    assert total_pendiente_acumulado(date(2026, 8, 31)) == 5000 - 36000


def test_eliminar_pago_de_faltante_revierte_inventario_y_pendiente(db, client):
    coca = crear_producto(db)
    stock_antes = calcular_stock(coca.id)
    pago = PagoFaltantePostobon(fecha=date(2026, 8, 20))
    pago.detalles = [PagoFaltantePostobonDetalle(producto_id=coca.id, cantidad_unidades=12, valor=36000)]
    db.session.add(pago)
    db.session.commit()
    assert calcular_stock(coca.id) == stock_antes + 12

    r = client.post(f"/postobon/pagos/{pago.id}/eliminar", follow_redirects=True)
    assert r.status_code == 200
    assert PagoFaltantePostobon.query.count() == 0
    assert calcular_stock(coca.id) == stock_antes
