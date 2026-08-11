from datetime import date

from sqlalchemy import func, or_

from extensions import db
from models import FacturaCartera


def total_pendiente(fecha_corte=None):
    """Dinero en cartera sin cobrar a la fecha de corte (hoy por defecto).
    Incluye facturas todavía pendientes, y facturas que en esa fecha aún no se habían
    pagado (se pagaron después de fecha_corte) — para que un reporte de un mes pasado
    muestre la cartera como estaba en ese momento, no como está hoy."""
    fecha_corte = fecha_corte or date.today()
    total = (
        db.session.query(func.coalesce(func.sum(FacturaCartera.monto), 0))
        .filter(FacturaCartera.fecha <= fecha_corte)
        .filter(
            or_(
                FacturaCartera.estado == "pendiente",
                FacturaCartera.fecha_pago > fecha_corte,
            )
        )
        .scalar()
    )
    return round(total)


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
