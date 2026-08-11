from sqlalchemy import func

from extensions import db
from models import CategoriaGasto, Gasto

CATEGORIAS_DEFAULT = {
    "negocio": [
        "Pago Postobón Transferencia",
        "Pago Postobón Contado",
        "Pago otros Distribuidores",
        "Pago Nómina",
    ],
    "hogar": [
        "Arriendo",
        "Luz",
        "Agua",
        "Compras",
    ],
}


def asegurar_categorias_default():
    """Crea las categorías iniciales si todavía no existen (no duplica si ya están)."""
    creadas = 0
    for tipo, nombres in CATEGORIAS_DEFAULT.items():
        for nombre in nombres:
            existe = CategoriaGasto.query.filter_by(nombre=nombre, tipo=tipo).first()
            if not existe:
                db.session.add(CategoriaGasto(nombre=nombre, tipo=tipo))
                creadas += 1
    if creadas:
        db.session.commit()
    return creadas


def categorias_por_tipo(tipo, solo_activas=True):
    query = CategoriaGasto.query.filter_by(tipo=tipo)
    if solo_activas:
        query = query.filter_by(activa=True)
    return query.order_by(CategoriaGasto.nombre).all()


def listar_gastos(tipo=None):
    query = Gasto.query.join(CategoriaGasto)
    if tipo:
        query = query.filter(CategoriaGasto.tipo == tipo)
    return query.order_by(Gasto.fecha.desc(), Gasto.id.desc()).all()


def total_gastos_periodo(fecha_inicio, fecha_fin, tipo=None):
    """fecha_inicio puede ser None para no poner límite inferior."""
    query = db.session.query(func.coalesce(func.sum(Gasto.monto), 0)).join(CategoriaGasto).filter(
        Gasto.fecha <= fecha_fin
    )
    if fecha_inicio is not None:
        query = query.filter(Gasto.fecha >= fecha_inicio)
    if tipo:
        query = query.filter(CategoriaGasto.tipo == tipo)
    return round(query.scalar())
