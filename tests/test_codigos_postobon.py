from datetime import date

import pytest

from models import Producto, ProductoPrecio, CodigoPostobon
from services.codigos_postobon import buscar_producto_por_codigo, listar_codigos


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


def test_buscar_producto_por_codigo_encuentra_el_producto_asignado(db):
    coca = crear_producto(db)
    db.session.add(CodigoPostobon(codigo="23929", producto_id=coca.id, notas="Naranja"))
    db.session.commit()

    assert buscar_producto_por_codigo("23929").id == coca.id


def test_buscar_producto_por_codigo_desconocido_devuelve_none(db):
    assert buscar_producto_por_codigo("99999") is None


def test_varios_codigos_pueden_apuntar_al_mismo_producto(db):
    gopack = crear_producto(db, "Pet 400 Gopack 400")
    db.session.add(CodigoPostobon(codigo="23929", producto_id=gopack.id, notas="Naranja"))
    db.session.add(CodigoPostobon(codigo="23215", producto_id=gopack.id, notas="Uva"))
    db.session.commit()

    assert buscar_producto_por_codigo("23929").id == gopack.id
    assert buscar_producto_por_codigo("23215").id == gopack.id
    assert len(listar_codigos()) == 2


def test_agregar_codigo_por_web(client, db):
    coca = crear_producto(db)
    r = client.post(
        "/postobon/codigos/nuevo",
        data={"codigo": "1412", "producto_id": str(coca.id), "notas": "Bolsa"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "1412" in body
    assert coca.nombre in body

    codigo = CodigoPostobon.query.one()
    assert codigo.codigo == "1412"
    assert codigo.producto_id == coca.id
    assert codigo.notas == "Bolsa"


def test_no_permite_asignar_el_mismo_codigo_dos_veces(client, db):
    coca = crear_producto(db, "Coca-Cola 1.5L")
    agua = crear_producto(db, "Agua Cristal")
    db.session.add(CodigoPostobon(codigo="1412", producto_id=coca.id))
    db.session.commit()

    r = client.post(
        "/postobon/codigos/nuevo",
        data={"codigo": "1412", "producto_id": str(agua.id)},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert CodigoPostobon.query.filter_by(codigo="1412").count() == 1
    assert CodigoPostobon.query.filter_by(codigo="1412").one().producto_id == coca.id


def test_eliminar_codigo(client, db):
    coca = crear_producto(db)
    codigo = CodigoPostobon(codigo="1412", producto_id=coca.id)
    db.session.add(codigo)
    db.session.commit()

    r = client.post(f"/postobon/codigos/{codigo.id}/eliminar", follow_redirects=True)
    assert r.status_code == 200
    assert CodigoPostobon.query.count() == 0
