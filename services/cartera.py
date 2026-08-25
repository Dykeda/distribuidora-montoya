from datetime import date

from sqlalchemy import func, or_

from extensions import db
from models import FacturaCartera, Cliente


def total_pendiente(fecha_corte=None, cliente_id=None):
    """Dinero en cartera sin cobrar a la fecha de corte (hoy por defecto).
    Incluye facturas todavía pendientes, y facturas que en esa fecha aún no se habían
    pagado (se pagaron después de fecha_corte) — para que un reporte de un mes pasado
    muestre la cartera como estaba en ese momento, no como está hoy. Con cliente_id,
    calcula el total pendiente de un solo cliente."""
    fecha_corte = fecha_corte or date.today()
    query = (
        db.session.query(func.coalesce(func.sum(FacturaCartera.monto), 0))
        .filter(FacturaCartera.fecha <= fecha_corte)
        .filter(
            or_(
                FacturaCartera.estado == "pendiente",
                FacturaCartera.fecha_pago > fecha_corte,
            )
        )
    )
    if cliente_id is not None:
        query = query.filter(FacturaCartera.cliente_id == cliente_id)
    return round(query.scalar())


def listar_facturas():
    return FacturaCartera.query.order_by(
        FacturaCartera.estado.desc(), FacturaCartera.fecha.desc()
    ).all()


def facturas_por_salida(salida_id):
    return (
        FacturaCartera.query.filter_by(salida_id=salida_id)
        .order_by(FacturaCartera.fecha.desc())
        .all()
    )


def listar_pendientes():
    """Todas las facturas de cartera sin cobrar, con el cliente cargado -- para el
    buscador de "créditos pagados" del cuadre de caja de una ruta."""
    return (
        FacturaCartera.query.filter_by(estado="pendiente")
        .join(Cliente)
        .order_by(Cliente.nombre, FacturaCartera.fecha)
        .all()
    )


def sincronizar_creditos_nuevos_en_ruta(retorno, salida, lineas):
    """Reemplaza todas las facturas de cartera que nacieron de este retorno (venta fiada
    ese día) con la lista nueva -- mismo patrón que sincronizar_gastos_en_ruta(). lineas es
    una lista de (cliente_id, monto, notas)."""
    FacturaCartera.query.filter_by(creada_en_retorno_id=retorno.id).delete()
    for cliente_id, monto, notas in lineas:
        if not cliente_id or not monto or monto <= 0:
            continue
        db.session.add(FacturaCartera(
            salida_id=salida.id, cliente_id=cliente_id, fecha=retorno.fecha, monto=monto,
            notas=notas or None, creada_en_retorno_id=retorno.id,
        ))


def sincronizar_creditos_pagados_en_ruta(retorno, factura_ids):
    """Marca como pagadas las facturas de cartera elegidas en el cuadre de esta ruta (el
    cliente le pagó una deuda vieja al conductor), y libera las que ya no estén elegidas
    -- para poder corregir si se edita el retorno, sin tocar facturas pagadas a mano desde
    Cartera (esas no tienen cobrada_en_retorno_id)."""
    liberadas = FacturaCartera.query.filter_by(cobrada_en_retorno_id=retorno.id)
    if factura_ids:
        liberadas = liberadas.filter(FacturaCartera.id.notin_(factura_ids))
    for f in liberadas.all():
        f.estado = "pendiente"
        f.fecha_pago = None
        f.cobrada_en_retorno_id = None

    for factura_id in factura_ids or []:
        factura = db.session.get(FacturaCartera, factura_id)
        if factura is None:
            continue
        factura.estado = "pagada"
        factura.fecha_pago = retorno.fecha
        factura.cobrada_en_retorno_id = retorno.id


def total_creditos_nuevos_en_ruta(retorno_id):
    total = (
        db.session.query(func.coalesce(func.sum(FacturaCartera.monto), 0))
        .filter(FacturaCartera.creada_en_retorno_id == retorno_id)
        .scalar()
    )
    return round(total)


def total_creditos_pagados_en_ruta(retorno_id):
    total = (
        db.session.query(func.coalesce(func.sum(FacturaCartera.monto), 0))
        .filter(FacturaCartera.cobrada_en_retorno_id == retorno_id)
        .scalar()
    )
    return round(total)


RANGOS_ANTIGUEDAD = [
    {"etiqueta": "0-15 días", "min": 0, "max": 15},
    {"etiqueta": "16-30 días", "min": 16, "max": 30},
    {"etiqueta": "31-60 días", "min": 31, "max": 60},
    {"etiqueta": "Más de 60 días", "min": 61, "max": None},
]


def _rango_de(dias):
    for r in RANGOS_ANTIGUEDAD:
        if dias >= r["min"] and (r["max"] is None or dias <= r["max"]):
            return r["etiqueta"]
    return RANGOS_ANTIGUEDAD[-1]["etiqueta"]


def facturas_con_antiguedad(fecha_referencia=None):
    """Todas las facturas, con los días que lleva pendiente cada una sin cobrar (None para
    las ya pagadas). Útil para ver de un vistazo cuáles llevan más tiempo sin cobrarse."""
    fecha_referencia = fecha_referencia or date.today()
    resultado = []
    for f in listar_facturas():
        dias = (fecha_referencia - f.fecha).days if f.estado == "pendiente" else None
        resultado.append({"factura": f, "dias_pendiente": dias})
    return resultado


def resumen_antiguedad(fecha_referencia=None):
    """Agrupa el dinero pendiente por cobrar en rangos de antigüedad (0-15, 16-30, 31-60,
    60+ días). Con un margen tan ajustado, la cartera vieja es el riesgo más directo al
    flujo de caja — este resumen lo hace visible sin tener que revisar factura por factura."""
    fecha_referencia = fecha_referencia or date.today()
    rangos = {r["etiqueta"]: {"etiqueta": r["etiqueta"], "monto": 0, "cantidad": 0} for r in RANGOS_ANTIGUEDAD}

    pendientes = FacturaCartera.query.filter_by(estado="pendiente").all()
    for f in pendientes:
        dias = (fecha_referencia - f.fecha).days
        etiqueta = _rango_de(dias)
        rangos[etiqueta]["monto"] += f.monto
        rangos[etiqueta]["cantidad"] += 1

    return [rangos[r["etiqueta"]] for r in RANGOS_ANTIGUEDAD]
