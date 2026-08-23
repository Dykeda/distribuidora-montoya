from sqlalchemy import func

from extensions import db
from models import CategoriaGasto, Gasto

CATEGORIAS_DEFAULT = {
    "negocio": [
        "Pago Postobón Transferencia",
        "Pago Postobón Contado",
        "Pago otros Distribuidores",
        "Pago Nómina",
        "Gasto en ruta",
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


def categoria_gasto_en_ruta():
    """Categoría "Gasto en ruta" (negocio) -- la crea si todavía no existe, para que el
    cuadre de caja de una ruta pueda generar su Gasto sin depender de que ya se haya
    corrido asegurar_categorias_default() en esta base de datos."""
    categoria = CategoriaGasto.query.filter_by(nombre="Gasto en ruta", tipo="negocio").first()
    if not categoria:
        categoria = CategoriaGasto(nombre="Gasto en ruta", tipo="negocio")
        db.session.add(categoria)
        db.session.flush()
    return categoria


def sincronizar_gasto_en_ruta(retorno, monto, fecha_salida):
    """Crea, actualiza o borra el Gasto de "Gasto en ruta" ligado a este retorno, para que
    el cuadre de caja de la ruta y la pantalla de Salidas de dinero siempre coincidan."""
    gasto = Gasto.query.filter_by(retorno_id=retorno.id).first()
    if monto and monto > 0:
        categoria = categoria_gasto_en_ruta()
        if gasto:
            gasto.monto = monto
            gasto.fecha = retorno.fecha
            gasto.categoria_id = categoria.id
        else:
            db.session.add(Gasto(
                categoria_id=categoria.id, fecha=retorno.fecha, monto=monto,
                notas=f"Gasto en ruta — salida del {fecha_salida.strftime('%Y-%m-%d')}",
                retorno_id=retorno.id,
            ))
    elif gasto:
        db.session.delete(gasto)


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
