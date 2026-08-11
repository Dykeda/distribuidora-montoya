from datetime import date

from models import SalidaCamion, FacturaCartera
from services.cartera import total_pendiente, listar_facturas, facturas_por_salida


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
