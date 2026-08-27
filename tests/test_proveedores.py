import pytest

from models import Proveedor
from services.proveedores import listar_proveedores, proveedor_postobon, resumen_proveedores


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
