from datetime import date

from sqlalchemy import func, or_

from extensions import db
from models import FacturaCartera


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
