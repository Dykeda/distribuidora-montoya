from extensions import db
from models import Proveedor


def listar_proveedores(solo_activos=True):
    query = Proveedor.query
    if solo_activos:
        query = query.filter_by(activo=True)
    return query.order_by(Proveedor.nombre).all()


def proveedor_postobon():
    """Proveedor "Postobón" (es_postobon=True) -- se crea solo si todavía no existe. Es el
    valor por defecto de Compra.proveedor_id (ver models.py), para que las compras
    antiguas o creadas sin especificar proveedor (pruebas incluidas) sigan asumiéndose
    como Postobón, el caso normal de este negocio."""
    proveedor = Proveedor.query.filter_by(nombre="Postobón").first()
    if proveedor is None:
        proveedor = Proveedor(nombre="Postobón", es_postobon=True)
        db.session.add(proveedor)
        db.session.flush()
    return proveedor


def resumen_proveedores():
    """Para cada proveedor activo: cuántas compras tiene -- para el listado."""
    return [{"proveedor": p, "cantidad_compras": len(p.compras)} for p in listar_proveedores()]
