from datetime import date

import pytest

from models import Producto, ProductoPrecio, Compra, CompraDetalle, Proveedor
from services.descuentos import total_descuento_periodo
from services.inventario import calcular_stock
from services.proveedores import proveedor_postobon


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"password": app.config["APP_PASSWORD"]})
    return c


def crear_producto(db, nombre="Coca-Cola 1.5L", precio=3000):
    p = Producto(nombre=nombre, unidades_por_caja=6, maneja_cajas=True, maneja_unidades=True)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, precio_venta_caja=precio * 6, vigente_desde=date(2026, 1, 1)))
    db.session.commit()
    return p


def test_eliminar_compra_borra_sus_lineas_y_recalcula_descuento_e_inventario(db, client):
    coca = crear_producto(db)
    compra = Compra(fecha=date(2026, 8, 5), numero_factura="F-001")
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=60,
            costo_linea=180000, tasa_descuento_aplicada=5.0, es_descuento=True,
        )
    )
    db.session.commit()
    compra_id = compra.id

    assert total_descuento_periodo(date(2026, 8, 1), date(2026, 8, 31)) == 180000
    assert calcular_stock(coca.id) == 60

    r = client.post(f"/compras/{compra_id}/eliminar", follow_redirects=True)
    assert r.status_code == 200

    assert Compra.query.get(compra_id) is None
    assert CompraDetalle.query.filter_by(compra_id=compra_id).count() == 0
    assert total_descuento_periodo(date(2026, 8, 1), date(2026, 8, 31)) == 0
    assert calcular_stock(coca.id) == 0


def test_eliminar_compra_inexistente_da_404(client):
    assert client.post("/compras/999/eliminar").status_code == 404


def test_nueva_compra_combina_cajas_y_unidades_sueltas(db, client):
    coca = crear_producto(db)  # 6 unidades por caja

    r = client.post(
        "/compras/nueva",
        data={
            "fecha": "2026-08-16",
            "numero_factura": "",
            "notas": "",
            "producto_id[]": [str(coca.id)],
            "cajas[]": ["2"],
            "unidades[]": ["3"],
            "costo_linea[]": ["45000"],
            "tasa_descuento[]": ["0"],
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert calcular_stock(coca.id) == 15  # 2*6 + 3


def test_nueva_compra_sin_proveedor_elegido_usa_postobon_por_defecto(db, client):
    coca = crear_producto(db)

    r = client.post(
        "/compras/nueva",
        data={
            "fecha": "2026-08-16", "numero_factura": "", "notas": "",
            "producto_id[]": [str(coca.id)], "cajas[]": ["1"], "unidades[]": ["0"],
            "costo_linea[]": ["18000"], "tasa_descuento[]": ["0"],
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    compra = Compra.query.one()
    assert compra.proveedor.nombre == "Postobón"
    assert compra.proveedor.es_postobon is True


def test_nueva_compra_con_proveedor_elegido_lo_guarda(db, client):
    coca = crear_producto(db)
    externo = Proveedor(nombre="Distribuidora XYZ", es_postobon=False)
    db.session.add(externo)
    db.session.commit()

    r = client.post(
        "/compras/nueva",
        data={
            "fecha": "2026-08-16", "numero_factura": "", "notas": "",
            "proveedor_id": str(externo.id),
            "producto_id[]": [str(coca.id)], "cajas[]": ["1"], "unidades[]": ["0"],
            "costo_linea[]": ["18000"], "tasa_descuento[]": ["0"],
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    compra = Compra.query.one()
    assert compra.proveedor_id == externo.id
    assert compra.proveedor.nombre == "Distribuidora XYZ"
    assert compra.proveedor.es_postobon is False


def test_lista_de_compras_muestra_el_proveedor(db, client):
    coca = crear_producto(db)
    compra = Compra(fecha=date(2026, 8, 16), proveedor_id=proveedor_postobon().id)
    db.session.add(compra)
    db.session.flush()
    db.session.add(CompraDetalle(
        compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=6, costo_linea=18000,
    ))
    db.session.commit()

    r = client.get("/compras/")
    assert "Postobón" in r.get_data(as_text=True)


def test_nueva_compra_calcula_neto_cuando_costo_incluye_iva(db, client):
    coca = crear_producto(db)

    r = client.post(
        "/compras/nueva",
        data={
            "fecha": "2026-08-16",
            "numero_factura": "",
            "notas": "",
            "producto_id[]": [str(coca.id)],
            "cajas[]": ["0"],
            "unidades[]": ["1"],
            "costo_linea[]": ["119000"],  # 100000 neto + 19% IVA
            "tasa_descuento[]": ["0"],
            "porcentaje_iva[]": ["19"],
            "costo_incluye_iva[]": ["1"],
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    detalle = CompraDetalle.query.filter_by(producto_id=coca.id).first()
    assert detalle.costo_linea == 100000
    assert detalle.valor_iva == 19000


def test_lista_y_detalle_de_compra_muestran_cajas_y_unidades_por_separado(db, client):
    coca = crear_producto(db)  # 6 unidades por caja
    compra = Compra(fecha=date(2026, 8, 5))
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=15,
            costo_linea=45000, tasa_descuento_aplicada=0.0,
        )
    )
    db.session.commit()

    r = client.get("/compras/")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Unidades compradas" not in body

    r = client.get(f"/compras/{compra.id}")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Cajas" in body and "Unidades sueltas" in body
    # 15 unidades = 2 cajas + 3 sueltas (6 u/caja)
    assert ">2<" in body
    assert ">3<" in body


def test_detalle_de_compra_producto_sin_cajas_muestra_todo_como_unidades_sueltas(db, client):
    agua = Producto(nombre="Agua Bolsa 6 Lts", unidades_por_caja=1, maneja_cajas=False, maneja_unidades=True)
    db.session.add(agua)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=agua.id, precio_venta_unidad=1000, precio_venta_caja=1000, vigente_desde=date(2026, 1, 1)))
    db.session.commit()

    compra = Compra(fecha=date(2026, 8, 16))
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(compra_id=compra.id, producto_id=agua.id, cantidad_comprada_unidades=8, costo_linea=8000, tasa_descuento_aplicada=0.0)
    )
    db.session.commit()

    r = client.get(f"/compras/{compra.id}")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    # 8 unidades sueltas, 0 cajas -- no debe verse "8" en la columna de Cajas
    filas = body.split("<tr>")
    fila_agua = next(f for f in filas if "Agua Bolsa 6 Lts" in f)
    assert ">0<" in fila_agua
    assert ">8<" in fila_agua


def _crear_compra_con_dos_productos(db):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    agua = crear_producto(db, "Agua Cristal", 2000)
    compra = Compra(fecha=date(2026, 8, 5), numero_factura="F-001")
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=60, costo_linea=180000, tasa_descuento_aplicada=5.0)
    )
    db.session.add(
        CompraDetalle(compra_id=compra.id, producto_id=agua.id, cantidad_comprada_unidades=12, costo_linea=24000, tasa_descuento_aplicada=10.0)
    )
    db.session.commit()
    return compra, coca, agua


def test_editar_linea_de_compra_actualiza_cantidad_costo_y_tasa(db, client):
    compra, coca, agua = _crear_compra_con_dos_productos(db)
    detalle_coca = next(d for d in compra.detalles if d.producto_id == coca.id)

    # de 60 unidades (10 cajas) a 8 cajas + 2 unidades = 50, costo y tasa distintos
    r = client.post(
        f"/compras/{compra.id}/linea/{detalle_coca.id}/editar",
        data={"cajas": "8", "unidades": "2", "costo_linea": "150000", "tasa_descuento": "7.5"},
        follow_redirects=True,
    )
    assert r.status_code == 200

    actualizado = CompraDetalle.query.get(detalle_coca.id)
    assert actualizado.cantidad_comprada_unidades == 50
    assert actualizado.costo_linea == 150000
    assert actualizado.tasa_descuento_aplicada == 7.5
    assert calcular_stock(coca.id) == 50


def test_agregar_linea_a_compra_existente(db, client):
    compra, coca, agua = _crear_compra_con_dos_productos(db)
    nuevo = crear_producto(db, nombre="Sprite 1.5L", precio=2500)

    r = client.post(
        f"/compras/{compra.id}/linea/nueva",
        data={
            "producto_id": str(nuevo.id), "cajas": "2", "unidades": "3",
            "costo_linea": "20000", "tasa_descuento": "10.0", "porcentaje_iva": "19",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    actualizado = Compra.query.get(compra.id)
    assert len(actualizado.detalles) == 3
    nueva_linea = next(d for d in actualizado.detalles if d.producto_id == nuevo.id)
    assert nueva_linea.cantidad_comprada_unidades == 15  # 2 cajas * 6 + 3 sueltas
    assert nueva_linea.costo_linea == 20000
    assert nueva_linea.tasa_descuento_aplicada == 10.0
    assert nueva_linea.porcentaje_iva == 19.0
    assert calcular_stock(nuevo.id) == 15


def test_agregar_linea_guarda_notas(db, client):
    compra, coca, agua = _crear_compra_con_dos_productos(db)

    r = client.post(
        f"/compras/{compra.id}/linea/nueva",
        data={
            "producto_id": str(coca.id), "cajas": "0", "unidades": "20",
            "costo_linea": "60000", "tasa_descuento": "9.2", "porcentaje_iva": "19",
            "notas": "Uva",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    nueva_linea = CompraDetalle.query.filter_by(compra_id=compra.id, tasa_descuento_aplicada=9.2).first()
    assert nueva_linea is not None
    assert nueva_linea.notas == "Uva"


def test_editar_linea_de_compra_actualiza_notas(db, client):
    compra, coca, agua = _crear_compra_con_dos_productos(db)
    detalle_coca = next(d for d in compra.detalles if d.producto_id == coca.id)

    r = client.post(
        f"/compras/{compra.id}/linea/{detalle_coca.id}/editar",
        data={"cajas": "10", "unidades": "0", "costo_linea": "180000", "tasa_descuento": "5.0", "notas": "sabor promo"},
        follow_redirects=True,
    )
    assert r.status_code == 200

    actualizado = CompraDetalle.query.get(detalle_coca.id)
    assert actualizado.notas == "sabor promo"


def test_dividir_un_producto_en_dos_lineas_con_tasas_distintas_detecta_faltante_solo_en_una(db, client):
    # Mismo producto (Pet 2,5 Gaseosa) facturado en dos líneas: la mayoría al 12% (sin
    # faltante) y la porción de Uva al 9.2% (sí hay faltante) -- sin crear "Uva" como
    # producto aparte en el catálogo.
    from services.postobon import listar_faltantes_de_compra

    p = crear_producto(db, "Pet 2,5 Gaseosa", 4000)
    p.tasa_descuento_referencia = 12.0
    compra = Compra(fecha=date(2026, 8, 20), numero_factura="AS001")
    db.session.add(compra)
    db.session.flush()
    db.session.add(CompraDetalle(
        compra_id=compra.id, producto_id=p.id, cantidad_comprada_unidades=80,
        costo_linea=280000, tasa_descuento_aplicada=12.0,
    ))
    db.session.add(CompraDetalle(
        compra_id=compra.id, producto_id=p.id, cantidad_comprada_unidades=20,
        costo_linea=72600, tasa_descuento_aplicada=9.2, notas="Uva",
    ))
    db.session.commit()

    faltantes = listar_faltantes_de_compra(compra.id)
    assert len(faltantes) == 1
    assert faltantes[0]["detalle"].notas == "Uva"
    assert faltantes[0]["diferencia_pct"] == 2.8

    r = client.get(f"/compras/{compra.id}")
    body = r.get_data(as_text=True)
    assert "Uva" in body


def test_agregar_linea_calcula_neto_cuando_costo_incluye_iva(db, client):
    compra, coca, agua = _crear_compra_con_dos_productos(db)
    nuevo = crear_producto(db, nombre="Sprite 1.5L", precio=2500)

    r = client.post(
        f"/compras/{compra.id}/linea/nueva",
        data={
            "producto_id": str(nuevo.id), "cajas": "0", "unidades": "1",
            "costo_linea": "119000", "tasa_descuento": "0", "porcentaje_iva": "19",
            "costo_incluye_iva": "1",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    nueva_linea = next(d for d in Compra.query.get(compra.id).detalles if d.producto_id == nuevo.id)
    assert nueva_linea.costo_linea == 100000
    assert nueva_linea.valor_iva == 19000


def test_editar_linea_calcula_neto_cuando_costo_incluye_iva(db, client):
    compra, coca, agua = _crear_compra_con_dos_productos(db)
    detalle_coca = next(d for d in compra.detalles if d.producto_id == coca.id)

    r = client.post(
        f"/compras/{compra.id}/linea/{detalle_coca.id}/editar",
        data={
            "cajas": "0", "unidades": "1", "costo_linea": "119000",
            "tasa_descuento": "0", "porcentaje_iva": "19", "costo_incluye_iva": "1",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    actualizado = CompraDetalle.query.get(detalle_coca.id)
    assert actualizado.costo_linea == 100000
    assert actualizado.valor_iva == 19000


def test_agregar_linea_sin_producto_no_agrega_nada(db, client):
    compra, coca, agua = _crear_compra_con_dos_productos(db)

    r = client.post(
        f"/compras/{compra.id}/linea/nueva",
        data={"producto_id": "", "cajas": "1", "unidades": "0", "costo_linea": "5000"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert len(Compra.query.get(compra.id).detalles) == 2


def test_eliminar_linea_de_compra_deja_el_resto_intacto(db, client):
    compra, coca, agua = _crear_compra_con_dos_productos(db)
    detalle_coca = next(d for d in compra.detalles if d.producto_id == coca.id)

    r = client.post(f"/compras/{compra.id}/linea/{detalle_coca.id}/eliminar", follow_redirects=True)
    assert r.status_code == 200

    assert Compra.query.get(compra.id) is not None
    assert len(Compra.query.get(compra.id).detalles) == 1
    assert calcular_stock(coca.id) == 0
    assert calcular_stock(agua.id) == 12


def test_eliminar_ultima_linea_de_compra_borra_la_compra_completa(db, client):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    compra = Compra(fecha=date(2026, 8, 5))
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=60, costo_linea=180000, tasa_descuento_aplicada=5.0)
    )
    db.session.commit()
    detalle = compra.detalles[0]

    r = client.post(f"/compras/{compra.id}/linea/{detalle.id}/eliminar", follow_redirects=True)
    assert r.status_code == 200
    assert Compra.query.get(compra.id) is None


def test_detalle_de_compra_muestra_subtotal_descuento_y_total(db, client):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    agua = crear_producto(db, "Agua Cristal", 2000)
    compra = Compra(fecha=date(2026, 8, 17), numero_factura="AS001")
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=60, costo_linea=180000, tasa_descuento_aplicada=10.0)
    )
    db.session.add(
        CompraDetalle(compra_id=compra.id, producto_id=agua.id, cantidad_comprada_unidades=9, costo_linea=9000, tasa_descuento_aplicada=0.0, es_descuento=True)
    )
    db.session.commit()

    r = client.get(f"/compras/{compra.id}")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    # bruto: 180000/0.9=200000 + 9000 (tasa 0) = 209000; descuento = 209000-189000 = 20000
    assert "209,000" in body  # subtotal (bruto)
    assert "20,000" in body  # descuento
    assert "189,000" in body  # total a pagar (sin IVA en ninguna línea)


def test_detalle_de_compra_sin_lineas_marcadas_no_muestra_insignia_de_descuento(db, client):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    compra = Compra(fecha=date(2026, 8, 17), numero_factura="AS001")
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=60, costo_linea=180000, tasa_descuento_aplicada=10.0)
    )
    db.session.commit()

    r = client.get(f"/compras/{compra.id}")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Descuento en producto" not in body


def test_detalle_de_compra_calcula_iva_por_linea_y_total_real(db, client):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)  # con IVA 19%
    agua = crear_producto(db, "Agua Cristal", 2000)  # sin IVA (agua embotellada)
    compra = Compra(fecha=date(2026, 8, 17), numero_factura="AS001")
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=60,
            costo_linea=100000, tasa_descuento_aplicada=10.0, porcentaje_iva=19.0,
        )
    )
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=agua.id, cantidad_comprada_unidades=30,
            costo_linea=50000, tasa_descuento_aplicada=0.0, porcentaje_iva=0.0,
        )
    )
    db.session.commit()

    detalle_coca = next(d for d in compra.detalles if d.producto_id == coca.id)
    assert detalle_coca.valor_iva == 19000  # 100000 * 19%

    r = client.get(f"/compras/{compra.id}")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    # coca: bruto=100000/0.9=111111, agua: bruto=50000 (tasa 0) -> subtotal=161111
    # IVA total = 19000 (solo la linea de coca), total a pagar = 150000+19000 = 169000
    assert "161,111" in body
    assert "19,000" in body
    assert "169,000" in body


def test_editar_linea_de_compra_guarda_porcentaje_iva(db, client):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    compra = Compra(fecha=date(2026, 8, 17), numero_factura="AS001")
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=60, costo_linea=100000, tasa_descuento_aplicada=0.0, porcentaje_iva=0.0)
    )
    db.session.commit()
    detalle = compra.detalles[0]

    r = client.post(
        f"/compras/{compra.id}/linea/{detalle.id}/editar",
        data={"cajas": "10", "unidades": "0", "costo_linea": "100000", "tasa_descuento": "0", "porcentaje_iva": "19"},
        follow_redirects=True,
    )
    assert r.status_code == 200

    actualizado = CompraDetalle.query.get(detalle.id)
    assert actualizado.porcentaje_iva == 19.0
    assert actualizado.valor_iva == 19000


def test_total_a_pagar_es_costo_mas_iva_sin_restar_el_descuento(db, client):
    coca = crear_producto(db, "Coca-Cola 1.5L", 3000)
    agua = crear_producto(db, "Agua Cristal", 2000)
    compra = Compra(fecha=date(2026, 8, 17), numero_factura="AS001")
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=60,
            costo_linea=100000, tasa_descuento_aplicada=10.0, porcentaje_iva=19.0,
        )
    )
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=agua.id, cantidad_comprada_unidades=30,
            costo_linea=50000, tasa_descuento_aplicada=0.0, porcentaje_iva=0.0, es_descuento=True,
        )
    )
    db.session.commit()

    r = client.get(f"/compras/{compra.id}")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    # coca: bruto=100000/0.9=111111 (descuento 11111), agua: bruto=50000 (tasa 0, descuento 0)
    # subtotal=161111, descuento=11111, IVA=19000, total a pagar = 150000+19000 = 169000
    assert "161,111" in body  # subtotal (bruto)
    assert "11,111" in body  # descuento
    assert "169,000" in body  # total a pagar = costo neto total + IVA (no resta el descuento otra vez)
