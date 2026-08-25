from datetime import date

import pytest

from models import SalidaCamion, RetornoCamion, FacturaCartera, Cliente
from services.cartera import (
    total_pendiente,
    listar_facturas,
    facturas_por_salida,
    facturas_con_antiguedad,
    resumen_antiguedad,
    listar_pendientes,
    sincronizar_creditos_nuevos_en_ruta,
    sincronizar_creditos_pagados_en_ruta,
    total_creditos_nuevos_en_ruta,
    total_creditos_pagados_en_ruta,
)


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"password": app.config["APP_PASSWORD"]})
    return c


def crear_salida(db, fecha=date(2026, 8, 2)):
    s = SalidaCamion(fecha=fecha)
    db.session.add(s)
    db.session.commit()
    return s


def crear_cliente(db, nombre):
    c = Cliente(nombre=nombre)
    db.session.add(c)
    db.session.commit()
    return c


def test_total_pendiente_solo_suma_facturas_pendientes(db):
    salida = crear_salida(db)
    ahorro = crear_cliente(db, "Tienda El Ahorro")
    sol = crear_cliente(db, "Minimarket Sol")
    db.session.add(
        FacturaCartera(salida_id=salida.id, cliente_id=ahorro.id, fecha=date(2026, 8, 2), monto=50000)
    )
    db.session.add(
        FacturaCartera(
            salida_id=salida.id, cliente_id=sol.id, fecha=date(2026, 8, 2),
            monto=30000, estado="pagada", fecha_pago=date(2026, 8, 5),
        )
    )
    db.session.commit()

    assert total_pendiente() == 50000
    assert len(listar_facturas()) == 2
    assert len(facturas_por_salida(salida.id)) == 2


def test_marcar_pagada_actualiza_el_total_pendiente(db):
    salida = crear_salida(db)
    ahorro = crear_cliente(db, "Tienda El Ahorro")
    factura = FacturaCartera(salida_id=salida.id, cliente_id=ahorro.id, fecha=date(2026, 8, 2), monto=50000)
    db.session.add(factura)
    db.session.commit()

    assert total_pendiente() == 50000

    factura.estado = "pagada"
    factura.fecha_pago = date(2026, 8, 6)
    db.session.commit()

    assert total_pendiente() == 0


def test_factura_sin_ruta_para_deudas_anteriores_al_sistema(db):
    vieja = crear_cliente(db, "Tienda Vieja")
    factura = FacturaCartera(
        salida_id=None, cliente_id=vieja.id, fecha=date(2026, 5, 1), monto=120000,
        notas="Deuda de antes de usar el sistema",
    )
    db.session.add(factura)
    db.session.commit()

    assert total_pendiente() == 120000
    assert listar_facturas()[0].salida is None


def test_facturas_con_antiguedad_solo_calcula_dias_para_pendientes(db):
    salida = crear_salida(db)
    ahorro = crear_cliente(db, "Tienda El Ahorro")
    sol = crear_cliente(db, "Minimarket Sol")
    db.session.add(
        FacturaCartera(salida_id=salida.id, cliente_id=ahorro.id, fecha=date(2026, 8, 2), monto=50000)
    )
    db.session.add(
        FacturaCartera(
            salida_id=salida.id, cliente_id=sol.id, fecha=date(2026, 7, 1),
            monto=30000, estado="pagada", fecha_pago=date(2026, 7, 10),
        )
    )
    db.session.commit()

    filas = facturas_con_antiguedad(fecha_referencia=date(2026, 8, 20))
    por_cliente = {f["factura"].cliente.nombre: f["dias_pendiente"] for f in filas}

    assert por_cliente["Tienda El Ahorro"] == 18
    assert por_cliente["Minimarket Sol"] is None


def test_resumen_antiguedad_agrupa_por_rango(db):
    salida = crear_salida(db)
    a, b, c, d, e = (crear_cliente(db, n) for n in "ABCDE")
    # 5 dias -> 0-15, 20 dias -> 16-30, 45 dias -> 31-60, 90 dias -> 60+
    db.session.add(FacturaCartera(salida_id=salida.id, cliente_id=a.id, fecha=date(2026, 8, 15), monto=10000))
    db.session.add(FacturaCartera(salida_id=salida.id, cliente_id=b.id, fecha=date(2026, 7, 31), monto=20000))
    db.session.add(FacturaCartera(salida_id=salida.id, cliente_id=c.id, fecha=date(2026, 7, 6), monto=30000))
    db.session.add(FacturaCartera(salida_id=salida.id, cliente_id=d.id, fecha=date(2026, 5, 22), monto=40000))
    # pagada -> no debe contar en ningún rango
    db.session.add(
        FacturaCartera(
            salida_id=salida.id, cliente_id=e.id, fecha=date(2026, 5, 1), monto=99999,
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


def test_eliminar_factura_la_quita_del_total_pendiente(db, client):
    salida = crear_salida(db)
    ahorro = crear_cliente(db, "Tienda El Ahorro")
    factura = FacturaCartera(salida_id=salida.id, cliente_id=ahorro.id, fecha=date(2026, 8, 2), monto=50000)
    db.session.add(factura)
    db.session.commit()
    factura_id = factura.id

    assert total_pendiente() == 50000

    r = client.post(f"/cartera/{factura_id}/eliminar", follow_redirects=True)
    assert r.status_code == 200

    assert FacturaCartera.query.get(factura_id) is None
    assert total_pendiente() == 0


def test_eliminar_factura_inexistente_da_404(client):
    assert client.post("/cartera/999/eliminar").status_code == 404


def crear_retorno(db, salida, fecha=date(2026, 8, 5)):
    r = RetornoCamion(salida_id=salida.id, fecha=fecha)
    db.session.add(r)
    db.session.commit()
    return r


def test_sincronizar_creditos_nuevos_en_ruta_crea_facturas_pendientes(db):
    salida = crear_salida(db)
    retorno = crear_retorno(db, salida)
    cliente = crear_cliente(db, "Tienda Nueva")

    sincronizar_creditos_nuevos_en_ruta(retorno, salida, [(cliente.id, 25000, "fiado")])
    db.session.commit()

    factura = FacturaCartera.query.filter_by(creada_en_retorno_id=retorno.id).one()
    assert factura.cliente_id == cliente.id
    assert factura.monto == 25000
    assert factura.estado == "pendiente"
    assert factura.salida_id == salida.id
    assert total_creditos_nuevos_en_ruta(retorno.id) == 25000


def test_sincronizar_creditos_nuevos_en_ruta_reemplaza_al_editar(db):
    salida = crear_salida(db)
    retorno = crear_retorno(db, salida)
    cliente = crear_cliente(db, "Tienda Nueva")

    sincronizar_creditos_nuevos_en_ruta(retorno, salida, [(cliente.id, 25000, "")])
    db.session.commit()

    sincronizar_creditos_nuevos_en_ruta(retorno, salida, [(cliente.id, 40000, "")])
    db.session.commit()

    facturas = FacturaCartera.query.filter_by(creada_en_retorno_id=retorno.id).all()
    assert len(facturas) == 1
    assert facturas[0].monto == 40000


def test_sincronizar_creditos_pagados_en_ruta_marca_y_libera(db):
    salida = crear_salida(db)
    retorno = crear_retorno(db, salida)
    cliente = crear_cliente(db, "Tienda Vieja")
    factura = FacturaCartera(cliente_id=cliente.id, fecha=date(2026, 7, 1), monto=15000, estado="pendiente")
    db.session.add(factura)
    db.session.commit()

    sincronizar_creditos_pagados_en_ruta(retorno, [factura.id])
    db.session.commit()

    assert factura.estado == "pagada"
    assert factura.fecha_pago == retorno.fecha
    assert factura.cobrada_en_retorno_id == retorno.id
    assert total_creditos_pagados_en_ruta(retorno.id) == 15000
    assert factura not in listar_pendientes()

    # se edita el retorno y se destilda esa factura -> vuelve a quedar pendiente
    sincronizar_creditos_pagados_en_ruta(retorno, [])
    db.session.commit()

    assert factura.estado == "pendiente"
    assert factura.fecha_pago is None
    assert factura.cobrada_en_retorno_id is None
    assert total_creditos_pagados_en_ruta(retorno.id) == 0


def test_sincronizar_creditos_pagados_no_toca_facturas_pagadas_a_mano(db):
    salida = crear_salida(db)
    retorno = crear_retorno(db, salida)
    cliente = crear_cliente(db, "Tienda Vieja")
    factura_manual = FacturaCartera(
        cliente_id=cliente.id, fecha=date(2026, 7, 1), monto=9000,
        estado="pagada", fecha_pago=date(2026, 7, 15),
    )
    db.session.add(factura_manual)
    db.session.commit()

    # el cuadre de esta ruta no elige ninguna factura -- no debe tocar la pagada a mano
    sincronizar_creditos_pagados_en_ruta(retorno, [])
    db.session.commit()

    assert factura_manual.estado == "pagada"
    assert factura_manual.fecha_pago == date(2026, 7, 15)
    assert factura_manual.cobrada_en_retorno_id is None
