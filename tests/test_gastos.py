from datetime import date

from models import CategoriaGasto, Gasto
from services.gastos import (
    categorias_por_tipo,
    listar_gastos,
    total_gastos_periodo,
    asegurar_categorias_default,
)


def test_categorias_default_quedan_creadas(db):
    negocio = categorias_por_tipo("negocio")
    hogar = categorias_por_tipo("hogar")
    nombres_negocio = {c.nombre for c in negocio}
    nombres_hogar = {c.nombre for c in hogar}

    assert "Pago Postobón Transferencia" in nombres_negocio
    assert "Pago Postobón Contado" in nombres_negocio
    assert "Pago otros Distribuidores" in nombres_negocio
    assert "Pago Nómina" in nombres_negocio
    assert "Arriendo" in nombres_hogar
    assert "Luz" in nombres_hogar
    assert "Agua" in nombres_hogar
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
