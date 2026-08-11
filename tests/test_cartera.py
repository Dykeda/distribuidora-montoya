from datetime import date

from models import SalidaCamion, FacturaCartera
from services.cartera import (
    total_pendiente,
    listar_facturas,
    facturas_por_salida,
    facturas_con_antiguedad,
    resumen_antiguedad,
)


def crear_salida(db, fecha=date(2026, 8, 2)):
    s = SalidaCamion(fecha=fecha)
    db.session.add(s)
    db.session.commit()
    return s


def test_total_pendiente_solo_suma_facturas_pendientes(db):
    salida = crear_salida(db)
    db.session.add(
        FacturaCartera(salida_id=salida.id, cliente="Tienda El Ahorro", fecha=date(2026, 8, 2), monto=50000)
    )
    db.session.add(
        FacturaCartera(
            salida_id=salida.id, cliente="Minimarket Sol", fecha=date(2026, 8, 2),
            monto=30000, estado="pagada", fecha_pago=date(2026, 8, 5),
        )
    )
    db.session.commit()

    assert total_pendiente() == 50000
    assert len(listar_facturas()) == 2
    assert len(facturas_por_salida(salida.id)) == 2


def test_marcar_pagada_actualiza_el_total_pendiente(db):
    salida = crear_salida(db)
    factura = FacturaCartera(salida_id=salida.id, cliente="Tienda El Ahorro", fecha=date(2026, 8, 2), monto=50000)
    db.session.add(factura)
    db.session.commit()

    assert total_pendiente() == 50000

    factura.estado = "pagada"
    factura.fecha_pago = date(2026, 8, 6)
    db.session.commit()

    assert total_pendiente() == 0


def test_factura_sin_ruta_para_deudas_anteriores_al_sistema(db):
    factura = FacturaCartera(
        salida_id=None, cliente="Tienda Vieja", fecha=date(2026, 5, 1), monto=120000,
        notas="Deuda de antes de usar el sistema",
    )
    db.session.add(factura)
    db.session.commit()

    assert total_pendiente() == 120000
    assert listar_facturas()[0].salida is None


def test_facturas_con_antiguedad_solo_calcula_dias_para_pendientes(db):
    salida = crear_salida(db)
    db.session.add(
        FacturaCartera(salida_id=salida.id, cliente="Tienda El Ahorro", fecha=date(2026, 8, 2), monto=50000)
    )
    db.session.add(
        FacturaCartera(
            salida_id=salida.id, cliente="Minimarket Sol", fecha=date(2026, 7, 1),
            monto=30000, estado="pagada", fecha_pago=date(2026, 7, 10),
        )
    )
    db.session.commit()

    filas = facturas_con_antiguedad(fecha_referencia=date(2026, 8, 20))
    por_cliente = {f["factura"].cliente: f["dias_pendiente"] for f in filas}

    assert por_cliente["Tienda El Ahorro"] == 18
    assert por_cliente["Minimarket Sol"] is None


def test_resumen_antiguedad_agrupa_por_rango(db):
    salida = crear_salida(db)
    # 5 dias -> 0-15, 20 dias -> 16-30, 45 dias -> 31-60, 90 dias -> 60+
    db.session.add(FacturaCartera(salida_id=salida.id, cliente="A", fecha=date(2026, 8, 15), monto=10000))
    db.session.add(FacturaCartera(salida_id=salida.id, cliente="B", fecha=date(2026, 7, 31), monto=20000))
    db.session.add(FacturaCartera(salida_id=salida.id, cliente="C", fecha=date(2026, 7, 6), monto=30000))
    db.session.add(FacturaCartera(salida_id=salida.id, cliente="D", fecha=date(2026, 5, 22), monto=40000))
    # pagada -> no debe contar en ningún rango
    db.session.add(
        FacturaCartera(
            salida_id=salida.id, cliente="E", fecha=date(2026, 5, 1), monto=99999,
            estado="pagada", fecha_pago=date(2026, 6, 1),
        )
    )
    db.session.commit()

    rangos = {r["etiqueta"]: r for r in resumen_antiguedad(fecha_referencia=date(2026, 8, 20))}

    assert rangos["0-15 días"]["monto"] == 10000
    assert rangos["0-15 días"]["cantidad"] == 1
    assert rangos["16-30 días"]["monto"] == 20000
    assert rangos["31-60 días"]["monto"] == 30000
    assert rangos["Más de 60 días"]["monto"] == 40000
    assert sum(r["monto"] for r in rangos.values()) == 100000
