from datetime import date, timedelta

import pytest

from models import CategoriaGasto, Gasto
from services.gastos import (
    categorias_por_tipo,
    listar_gastos,
    total_gastos_periodo,
    totales_por_categoria,
    asegurar_categorias_default,
    fusionar_categorias,
)


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"password": app.config["APP_PASSWORD"]})
    return c


def test_categorias_default_quedan_creadas(db):
    negocio = categorias_por_tipo("negocio")
    hogar = categorias_por_tipo("hogar")
    nombres_negocio = {c.nombre for c in negocio}
    nombres_hogar = {c.nombre for c in hogar}

    assert "Pago Postobón Transferencia" in nombres_negocio
    assert "Pago Postobón Contado" in nombres_negocio
    assert "Pago otros Distribuidores" in nombres_negocio
    assert "Pago Nómina" in nombres_negocio
    assert "Gasto en ruta" in nombres_negocio
    assert "Arriendo" in nombres_hogar
    assert "Servicios públicos" in nombres_hogar
    assert "Compras" in nombres_hogar


def test_asegurar_categorias_default_no_duplica(db):
    antes = CategoriaGasto.query.count()
    creadas = asegurar_categorias_default()
    despues = CategoriaGasto.query.count()

    assert creadas == 0
    assert antes == despues


def test_total_gastos_periodo_filtra_por_tipo(db):
    cat_negocio = CategoriaGasto.query.filter_by(nombre="Pago Nómina", tipo="negocio").first()
    cat_hogar = CategoriaGasto.query.filter_by(nombre="Arriendo", tipo="hogar").first()

    db.session.add(Gasto(categoria_id=cat_negocio.id, fecha=date(2026, 8, 5), monto=500000))
    db.session.add(Gasto(categoria_id=cat_hogar.id, fecha=date(2026, 8, 5), monto=800000))
    db.session.commit()

    assert total_gastos_periodo(date(2026, 8, 1), date(2026, 8, 31)) == 1300000
    assert total_gastos_periodo(date(2026, 8, 1), date(2026, 8, 31), tipo="negocio") == 500000
    assert total_gastos_periodo(date(2026, 8, 1), date(2026, 8, 31), tipo="hogar") == 800000

    todos = listar_gastos()
    assert len(todos) == 2
    solo_negocio = listar_gastos(tipo="negocio")
    assert len(solo_negocio) == 1
    assert solo_negocio[0].categoria.nombre == "Pago Nómina"


def test_fusionar_categorias_mueve_gastos_y_desactiva_las_de_origen(db):
    luz = CategoriaGasto(nombre="Luz", tipo="hogar")
    agua = CategoriaGasto(nombre="Agua", tipo="hogar")
    db.session.add_all([luz, agua])
    db.session.flush()
    db.session.add(Gasto(categoria_id=luz.id, fecha=date(2026, 8, 5), monto=50000))
    db.session.add(Gasto(categoria_id=agua.id, fecha=date(2026, 8, 5), monto=30000))
    db.session.commit()

    destino, movidos = fusionar_categorias(["Luz", "Agua"], "hogar", "Servicios públicos")

    assert movidos == 2
    assert destino.nombre == "Servicios públicos"
    assert total_gastos_periodo(date(2026, 8, 1), date(2026, 8, 31), tipo="hogar") == 80000

    nombres_hogar_activas = {c.nombre for c in categorias_por_tipo("hogar")}
    assert "Luz" not in nombres_hogar_activas
    assert "Agua" not in nombres_hogar_activas
    assert "Servicios públicos" in nombres_hogar_activas

    gasto_luz = Gasto.query.filter_by(categoria_id=luz.id).first()
    assert gasto_luz is None  # ya no queda ningún Gasto en la categoria vieja
    assert Gasto.query.filter_by(categoria_id=destino.id).count() == 2


def test_totales_por_categoria_agrupa_y_ordena_de_mayor_a_menor(db):
    cat_nomina = CategoriaGasto.query.filter_by(nombre="Pago Nómina", tipo="negocio").first()
    cat_arriendo = CategoriaGasto.query.filter_by(nombre="Arriendo", tipo="hogar").first()

    db.session.add(Gasto(categoria_id=cat_nomina.id, fecha=date(2026, 8, 5), monto=100000))
    db.session.add(Gasto(categoria_id=cat_nomina.id, fecha=date(2026, 8, 10), monto=50000))
    db.session.add(Gasto(categoria_id=cat_arriendo.id, fecha=date(2026, 8, 1), monto=800000))
    db.session.commit()

    totales = totales_por_categoria()
    assert totales[0]["categoria"].nombre == "Arriendo"
    assert totales[0]["total"] == 800000
    assert totales[1]["categoria"].nombre == "Pago Nómina"
    assert totales[1]["total"] == 150000

    solo_negocio = totales_por_categoria(tipo="negocio")
    assert len(solo_negocio) == 1
    assert solo_negocio[0]["categoria"].nombre == "Pago Nómina"

    solo_agosto = totales_por_categoria(fecha_inicio=date(2026, 8, 1), fecha_fin=date(2026, 8, 9))
    nombres = {f["categoria"].nombre for f in solo_agosto}
    assert nombres == {"Pago Nómina", "Arriendo"}
    total_nomina_parcial = next(f["total"] for f in solo_agosto if f["categoria"].nombre == "Pago Nómina")
    assert total_nomina_parcial == 100000  # solo la del 5 de agosto, no la del 10


def test_listar_gastos_filtra_por_categoria_y_periodo(db):
    cat_nomina = CategoriaGasto.query.filter_by(nombre="Pago Nómina", tipo="negocio").first()
    cat_arriendo = CategoriaGasto.query.filter_by(nombre="Arriendo", tipo="hogar").first()

    db.session.add(Gasto(categoria_id=cat_nomina.id, fecha=date(2026, 7, 15), monto=100000))
    db.session.add(Gasto(categoria_id=cat_nomina.id, fecha=date(2026, 8, 15), monto=200000))
    db.session.add(Gasto(categoria_id=cat_arriendo.id, fecha=date(2026, 8, 1), monto=800000))
    db.session.commit()

    solo_nomina = listar_gastos(categoria_id=cat_nomina.id)
    assert len(solo_nomina) == 2

    solo_agosto = listar_gastos(fecha_inicio=date(2026, 8, 1), fecha_fin=date(2026, 8, 31))
    assert len(solo_agosto) == 2

    nomina_agosto = listar_gastos(categoria_id=cat_nomina.id, fecha_inicio=date(2026, 8, 1), fecha_fin=date(2026, 8, 31))
    assert len(nomina_agosto) == 1
    assert nomina_agosto[0].monto == 200000


def test_pagina_gastos_filtra_por_mes_y_muestra_totales_por_categoria(db, client):
    cat_nomina = CategoriaGasto.query.filter_by(nombre="Pago Nómina", tipo="negocio").first()

    db.session.add(Gasto(categoria_id=cat_nomina.id, fecha=date(2026, 7, 15), monto=100000))
    db.session.add(Gasto(categoria_id=cat_nomina.id, fecha=date(2026, 8, 15), monto=200000))
    db.session.commit()

    r = client.get("/gastos/?periodo=mes&anio=2026&mes=8")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "200,000" in body
    assert "100,000" not in body  # julio queda afuera del filtro


def test_editar_gasto_actualiza_categoria_monto_y_fecha(db, client):
    cat_nomina = CategoriaGasto.query.filter_by(nombre="Pago Nómina", tipo="negocio").first()
    cat_transferencia = CategoriaGasto.query.filter_by(
        nombre="Pago Postobón Transferencia", tipo="negocio"
    ).first()
    gasto = Gasto(categoria_id=cat_nomina.id, fecha=date(2026, 9, 1), monto=100000)
    db.session.add(gasto)
    db.session.commit()

    r = client.post(
        f"/gastos/{gasto.id}/editar",
        data={
            "categoria_id": str(cat_transferencia.id),
            "fecha": "2026-09-05",
            "monto": "250000",
            "notas": "Corregido",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    actualizado = db.session.get(Gasto, gasto.id)
    assert actualizado.categoria_id == cat_transferencia.id
    assert actualizado.fecha == date(2026, 9, 5)
    assert actualizado.monto == 250000
    assert actualizado.notas == "Corregido"


def test_editar_gasto_de_ruta_se_bloquea(db, client):
    cat = CategoriaGasto.query.filter_by(nombre="Gasto en ruta", tipo="negocio").first()
    gasto = Gasto(categoria_id=cat.id, fecha=date(2026, 9, 1), monto=50000, retorno_id=1)
    db.session.add(gasto)
    db.session.commit()

    r = client.post(
        f"/gastos/{gasto.id}/editar",
        data={"categoria_id": str(cat.id), "fecha": "2026-09-05", "monto": "999999"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "edítala desde el cuadre de esa ruta" in r.get_data(as_text=True)

    sin_cambios = db.session.get(Gasto, gasto.id)
    assert sin_cambios.monto == 50000


def test_eliminar_gasto(db, client):
    cat = CategoriaGasto.query.filter_by(nombre="Pago Nómina", tipo="negocio").first()
    gasto = Gasto(categoria_id=cat.id, fecha=date(2026, 9, 1), monto=100000)
    db.session.add(gasto)
    db.session.commit()
    gasto_id = gasto.id

    r = client.post(f"/gastos/{gasto_id}/eliminar", follow_redirects=True)
    assert r.status_code == 200
    assert db.session.get(Gasto, gasto_id) is None


def test_eliminar_gasto_de_ruta_se_bloquea(db, client):
    cat = CategoriaGasto.query.filter_by(nombre="Gasto en ruta", tipo="negocio").first()
    gasto = Gasto(categoria_id=cat.id, fecha=date(2026, 9, 1), monto=50000, retorno_id=1)
    db.session.add(gasto)
    db.session.commit()
    gasto_id = gasto.id

    r = client.post(f"/gastos/{gasto_id}/eliminar", follow_redirects=True)
    assert r.status_code == 200
    assert db.session.get(Gasto, gasto_id) is not None


def test_pagina_gastos_por_defecto_muestra_solo_el_mes_actual(db, client):
    cat = CategoriaGasto.query.filter_by(nombre="Pago Nómina", tipo="negocio").first()
    hoy = date.today()
    mes_pasado = hoy.replace(day=1) - timedelta(days=1)
    db.session.add(Gasto(categoria_id=cat.id, fecha=hoy, monto=111000, notas="de este mes"))
    db.session.add(Gasto(categoria_id=cat.id, fecha=mes_pasado, monto=222000, notas="del mes pasado"))
    db.session.commit()

    cuerpo = client.get("/gastos/").get_data(as_text=True)
    assert "de este mes" in cuerpo
    assert "del mes pasado" not in cuerpo
    assert 'id="buscador-tabla"' in cuerpo

    # Los meses anteriores siguen disponibles eligiéndolos, y el histórico completo también.
    anterior = client.get(f"/gastos/?anio={mes_pasado.year}&mes={mes_pasado.month}").get_data(as_text=True)
    assert "del mes pasado" in anterior and "de este mes" not in anterior
    todo = client.get("/gastos/?periodo=todo").get_data(as_text=True)
    assert "del mes pasado" in todo and "de este mes" in todo


def test_pagina_gastos_filtra_por_rango_de_fechas_y_tolera_parametros_invalidos(db, client):
    cat = CategoriaGasto.query.filter_by(nombre="Pago Nómina", tipo="negocio").first()
    for dia, nota in ((5, "dia cinco"), (12, "dia doce"), (20, "dia veinte")):
        db.session.add(Gasto(categoria_id=cat.id, fecha=date(2026, 8, dia), monto=1000, notas=nota))
    db.session.commit()

    cuerpo = client.get("/gastos/?periodo=rango&desde=2026-08-10&hasta=2026-08-15").get_data(as_text=True)
    assert "dia doce" in cuerpo
    assert "dia cinco" not in cuerpo and "dia veinte" not in cuerpo

    # Un día exacto (desde = hasta) sirve para ubicar una ruta puntual.
    exacto = client.get("/gastos/?periodo=rango&desde=2026-08-20&hasta=2026-08-20").get_data(as_text=True)
    assert "dia veinte" in exacto and "dia doce" not in exacto

    # Parámetros inválidos no rompen la pantalla.
    assert client.get("/gastos/?mes=99&anio=abc").status_code == 200
    assert client.get("/gastos/?periodo=raro&desde=basura").status_code == 200
