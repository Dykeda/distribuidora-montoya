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
        "Servicios públicos",
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


def fusionar_categorias(nombres_origen, tipo, nombre_destino):
    """Junta varias categorías del mismo tipo en una sola -- mueve todos los Gasto de las
    categorías de origen a la de destino (la crea si no existe) y desactiva las de
    origen, sin borrar nada del historial."""
    destino = CategoriaGasto.query.filter_by(nombre=nombre_destino, tipo=tipo).first()
    if not destino:
        destino = CategoriaGasto(nombre=nombre_destino, tipo=tipo)
        db.session.add(destino)
        db.session.flush()

    movidos = 0
    for nombre in nombres_origen:
        origen = CategoriaGasto.query.filter_by(nombre=nombre, tipo=tipo).first()
        if not origen or origen.id == destino.id:
            continue
        movidos += Gasto.query.filter_by(categoria_id=origen.id).update({"categoria_id": destino.id})
        origen.activa = False
    db.session.commit()
    return destino, movidos


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


def gastos_en_ruta(retorno_id):
    """Todos los Gasto ligados a un retorno -- una ruta puede tener varios (gasolina,
    un pago a Postobón hecho en el camino, etc.)."""
    return Gasto.query.filter_by(retorno_id=retorno_id).order_by(Gasto.id).all()


def total_gasto_en_ruta(retorno_id):
    return db.session.query(func.coalesce(func.sum(Gasto.monto), 0)).filter(
        Gasto.retorno_id == retorno_id
    ).scalar()


def sincronizar_gastos_en_ruta(retorno, lineas, fecha_salida):
    """Reemplaza todos los Gasto ligados a este retorno con la lista nueva, para que el
    cuadre de caja de la ruta y Salidas de dinero siempre coincidan. lineas es una lista
    de (categoria_id_o_None, monto) -- categoria_id None cae en la categoría genérica
    "Gasto en ruta"."""
    Gasto.query.filter_by(retorno_id=retorno.id).delete()
    for categoria_id, monto in lineas:
        if not monto or monto <= 0:
            continue
        categoria = db.session.get(CategoriaGasto, categoria_id) if categoria_id else None
        if categoria is None:
            categoria = categoria_gasto_en_ruta()
        db.session.add(Gasto(
            categoria_id=categoria.id, fecha=retorno.fecha, monto=monto,
            notas=f"Gasto en ruta — salida del {fecha_salida.strftime('%Y-%m-%d')}",
            retorno_id=retorno.id,
        ))


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
