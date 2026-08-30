from datetime import date

import pytest

from models import Compra, CompraDetalle, Producto, ProductoPrecio, Proveedor
from services.proveedores import (
    listar_proveedores, proveedor_postobon, resumen_proveedores,
    resumen_compras_proveedor, total_descuento_proveedor,
)


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"password": app.config["APP_PASSWORD"]})
    return c


def crear_proveedor(db, nombre, es_postobon=False):
    p = Proveedor(nombre=nombre, es_postobon=es_postobon)
    db.session.add(p)
    db.session.commit()
    return p


def crear_producto(db, nombre="Hit 500ml", unidades_por_caja=6):
    p = Producto(nombre=nombre, unidades_por_caja=unidades_por_caja, maneja_cajas=True, maneja_unidades=True)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=1500, precio_venta_caja=1500 * unidades_por_caja, vigente_desde=date(2026, 1, 1)))
    db.session.commit()
    return p


def test_proveedor_postobon_se_crea_solo_la_primera_vez(db):
    p1 = proveedor_postobon()
    p2 = proveedor_postobon()

    assert p1.id == p2.id
    assert p1.nombre == "Postobón"
    assert p1.es_postobon is True
    assert Proveedor.query.filter_by(nombre="Postobón").count() == 1


def test_listar_proveedores_solo_activos_por_defecto(db):
    activo = crear_proveedor(db, "Activo")
    inactivo = crear_proveedor(db, "Inactivo")
    inactivo.activo = False
    db.session.commit()

    nombres = [p.nombre for p in listar_proveedores()]
    assert "Activo" in nombres
    assert "Inactivo" not in nombres
    assert len(listar_proveedores(solo_activos=False)) == 2


def test_resumen_proveedores_cuenta_compras(db):
    from datetime import date
    from models import Compra

    xyz = crear_proveedor(db, "Distribuidora XYZ")
    db.session.add(Compra(fecha=date(2026, 8, 1), proveedor_id=xyz.id))
    db.session.add(Compra(fecha=date(2026, 8, 2), proveedor_id=xyz.id))
    db.session.commit()

    resumen = {r["proveedor"].nombre: r["cantidad_compras"] for r in resumen_proveedores()}
    assert resumen["Distribuidora XYZ"] == 2


def test_crear_proveedor_por_web(client, db):
    r = client.post("/proveedores/nuevo", data={"nombre": "Distribuidora XYZ", "notas": "compra ocasional"}, follow_redirects=True)
    assert r.status_code == 200

    proveedor = Proveedor.query.filter_by(nombre="Distribuidora XYZ").first()
    assert proveedor is not None
    assert proveedor.notas == "compra ocasional"
    assert proveedor.es_postobon is False


def test_no_permite_dos_proveedores_con_el_mismo_nombre(client, db):
    crear_proveedor(db, "Proveedor Repetido")
    r = client.post("/proveedores/nuevo", data={"nombre": "Proveedor Repetido"}, follow_redirects=True)
    assert r.status_code == 200
    assert Proveedor.query.filter_by(nombre="Proveedor Repetido").count() == 1


def test_crear_proveedor_por_ajax_devuelve_json_y_marca_no_postobon(client, db):
    r = client.post("/proveedores/nuevo-ajax", json={"nombre": "Proveedor AJAX"})
    assert r.status_code == 201
    proveedor = Proveedor.query.filter_by(nombre="Proveedor AJAX").one()
    assert r.get_json() == {"id": proveedor.id, "nombre": "Proveedor AJAX"}
    assert proveedor.es_postobon is False


def test_crear_proveedor_por_ajax_sin_nombre_da_error(client, db):
    r = client.post("/proveedores/nuevo-ajax", json={"nombre": "  "})
    assert r.status_code == 400
    assert Proveedor.query.count() == 0


def test_crear_proveedor_por_ajax_no_permite_nombre_repetido(client, db):
    crear_proveedor(db, "Proveedor Repetido AJAX")
    r = client.post("/proveedores/nuevo-ajax", json={"nombre": "Proveedor Repetido AJAX"})
    assert r.status_code == 400
    assert Proveedor.query.filter_by(nombre="Proveedor Repetido AJAX").count() == 1


def test_editar_proveedor(client, db):
    p = crear_proveedor(db, "Nombre Viejo")
    r = client.post(
        f"/proveedores/{p.id}/editar",
        data={"nombre": "Nombre Nuevo", "notas": "actualizado"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert p.nombre == "Nombre Nuevo"
    assert p.notas == "actualizado"


def test_desactivar_proveedor_lo_saca_del_listado_activo(client, db):
    p = crear_proveedor(db, "Proveedor a Desactivar")
    r = client.post(f"/proveedores/{p.id}/desactivar", follow_redirects=True)
    assert r.status_code == 200
    assert p.activo is False
    assert p.nombre not in [x.nombre for x in listar_proveedores()]


def test_resumen_compras_proveedor_suma_cantidad_costo_y_descuento_por_producto(db):
    canasto = crear_proveedor(db, "Canasto")
    hit = crear_producto(db, "Hit 500ml", unidades_por_caja=6)
    compra = Compra(fecha=date(2026, 8, 16), proveedor_id=canasto.id)
    db.session.add(compra)
    db.session.flush()
    # 86 cajas pagadas ($2,580,000) + 14 cajas de descuento (gratis), igual que en el
    # detalle de una compra: bruto=3,000,000, descuento=420,000.
    db.session.add(CompraDetalle(
        compra_id=compra.id, producto_id=hit.id, cantidad_comprada_unidades=86 * 6,
        costo_linea=2580000, tasa_descuento_aplicada=14.0, es_descuento=False,
    ))
    db.session.add(CompraDetalle(
        compra_id=compra.id, producto_id=hit.id, cantidad_comprada_unidades=14 * 6,
        costo_linea=0, tasa_descuento_aplicada=0.0, es_descuento=True,
    ))
    db.session.commit()

    filas = resumen_compras_proveedor(canasto.id, date(2026, 8, 1), date(2026, 8, 31))
    assert len(filas) == 1
    fila = filas[0]
    assert fila["producto"].nombre == "Hit 500ml"
    assert fila["cajas"] == 100
    assert fila["unidades_sueltas"] == 0
    assert fila["costo_pagado"] == 2580000
    assert fila["descuento"] == 420000


def test_total_descuento_proveedor_no_se_reinicia_entre_meses(db):
    canasto = crear_proveedor(db, "Canasto")
    hit = crear_producto(db, "Hit 500ml", unidades_por_caja=6)

    compra_agosto = Compra(fecha=date(2026, 8, 16), proveedor_id=canasto.id)
    db.session.add(compra_agosto)
    db.session.flush()
    db.session.add(CompraDetalle(
        compra_id=compra_agosto.id, producto_id=hit.id, cantidad_comprada_unidades=86 * 6,
        costo_linea=2580000, tasa_descuento_aplicada=14.0,
    ))
    db.session.add(CompraDetalle(
        compra_id=compra_agosto.id, producto_id=hit.id, cantidad_comprada_unidades=14 * 6,
        costo_linea=0, tasa_descuento_aplicada=0.0, es_descuento=True,
    ))

    compra_septiembre = Compra(fecha=date(2026, 9, 3), proveedor_id=canasto.id)
    db.session.add(compra_septiembre)
    db.session.flush()
    db.session.add(CompraDetalle(
        compra_id=compra_septiembre.id, producto_id=hit.id, cantidad_comprada_unidades=45 * 6,
        costo_linea=1350000, tasa_descuento_aplicada=10.0,
    ))
    db.session.add(CompraDetalle(
        compra_id=compra_septiembre.id, producto_id=hit.id, cantidad_comprada_unidades=5 * 6,
        costo_linea=0, tasa_descuento_aplicada=0.0, es_descuento=True,
    ))
    db.session.commit()

    descuento_agosto = total_descuento_proveedor(canasto.id, date(2026, 8, 1), date(2026, 8, 31))
    descuento_septiembre = total_descuento_proveedor(canasto.id, date(2026, 9, 1), date(2026, 9, 30))
    descuento_acumulado_a_septiembre = total_descuento_proveedor(canasto.id, date(2000, 1, 1), date(2026, 9, 30))

    assert descuento_agosto == 420000
    assert descuento_septiembre == 150000
    assert descuento_acumulado_a_septiembre == 570000  # 420,000 + 150,000 -- no se reinicia


def test_pagina_de_proveedor_muestra_cards_y_tabla_por_mes(client, db):
    canasto = crear_proveedor(db, "Canasto")
    hit = crear_producto(db, "Hit 500ml", unidades_por_caja=6)
    compra = Compra(fecha=date(2026, 8, 16), proveedor_id=canasto.id)
    db.session.add(compra)
    db.session.flush()
    db.session.add(CompraDetalle(
        compra_id=compra.id, producto_id=hit.id, cantidad_comprada_unidades=86 * 6,
        costo_linea=2580000, tasa_descuento_aplicada=14.0,
    ))
    db.session.add(CompraDetalle(
        compra_id=compra.id, producto_id=hit.id, cantidad_comprada_unidades=14 * 6,
        costo_linea=0, tasa_descuento_aplicada=0.0, es_descuento=True,
    ))
    db.session.commit()

    r = client.get(f"/proveedores/{canasto.id}?mes=8&anio=2026")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Hit 500ml" in body
    assert "420,000" in body  # descuento del mes (aparece en la card y en el total de la tabla)
    assert "2,580,000" in body  # costo pagado

    r = client.get(f"/proveedores/{canasto.id}?mes=9&anio=2026")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "No hay compras a este proveedor en este mes." in body
    assert "420,000" in body  # el acumulado histórico sigue mostrando lo de agosto
