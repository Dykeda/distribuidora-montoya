from datetime import date

import pytest

from models import Cliente, FacturaCartera
from services.clientes import listar_clientes, resumen_clientes


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"password": app.config["APP_PASSWORD"]})
    return c


def crear_cliente(db, nombre):
    c = Cliente(nombre=nombre)
    db.session.add(c)
    db.session.commit()
    return c


def test_resumen_clientes_cuenta_facturas_y_pendiente_por_cliente(db):
    ana = crear_cliente(db, "Tienda Ana")
    beto = crear_cliente(db, "Tienda Beto")

    db.session.add(FacturaCartera(cliente_id=ana.id, fecha=date(2026, 8, 1), monto=10000))
    db.session.add(FacturaCartera(cliente_id=ana.id, fecha=date(2026, 8, 2), monto=15000))
    db.session.add(
        FacturaCartera(
            cliente_id=ana.id, fecha=date(2026, 8, 3), monto=5000,
            estado="pagada", fecha_pago=date(2026, 8, 4),
        )
    )
    db.session.add(FacturaCartera(cliente_id=beto.id, fecha=date(2026, 8, 1), monto=7000))
    db.session.commit()

    resumen = {r["cliente"].nombre: r for r in resumen_clientes()}

    assert resumen["Tienda Ana"]["cantidad_facturas"] == 3
    assert resumen["Tienda Ana"]["total_pendiente"] == 25000  # solo las 2 pendientes
    assert resumen["Tienda Beto"]["cantidad_facturas"] == 1
    assert resumen["Tienda Beto"]["total_pendiente"] == 7000


def test_listar_clientes_solo_activos_por_defecto(db):
    activo = crear_cliente(db, "Activo")
    inactivo = crear_cliente(db, "Inactivo")
    inactivo.activo = False
    db.session.commit()

    nombres = [c.nombre for c in listar_clientes()]
    assert "Activo" in nombres
    assert "Inactivo" not in nombres
    assert len(listar_clientes(solo_activos=False)) == 2


def test_crear_cliente_por_web_y_usarlo_en_una_factura(client, db):
    r = client.post("/clientes/nuevo", data={"nombre": "Distribuidora XYZ", "notas": "Cliente frecuente"}, follow_redirects=True)
    assert r.status_code == 200

    cliente = Cliente.query.filter_by(nombre="Distribuidora XYZ").first()
    assert cliente is not None
    assert cliente.notas == "Cliente frecuente"

    r = client.post(
        "/cartera/nueva",
        data={"cliente_id": str(cliente.id), "salida_id": "", "fecha": "2026-08-10", "monto": "30000", "notas": ""},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert len(cliente.facturas) == 1

    r = client.get(f"/clientes/{cliente.id}")
    assert r.status_code == 200
    assert "Distribuidora XYZ" in r.get_data(as_text=True)
    assert "30,000" in r.get_data(as_text=True)


def test_no_permite_dos_clientes_con_el_mismo_nombre(client, db):
    crear_cliente(db, "Tienda Repetida")
    r = client.post("/clientes/nuevo", data={"nombre": "Tienda Repetida", "notas": ""}, follow_redirects=True)
    assert r.status_code == 200
    assert Cliente.query.filter_by(nombre="Tienda Repetida").count() == 1


def test_desactivar_cliente_lo_saca_del_listado_activo(client, db):
    c = crear_cliente(db, "Tienda a Desactivar")
    r = client.post(f"/clientes/{c.id}/desactivar", follow_redirects=True)
    assert r.status_code == 200
    assert c.activo is False
    assert c.nombre not in [x.nombre for x in listar_clientes()]
