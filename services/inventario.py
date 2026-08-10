from sqlalchemy import func

from extensions import db
from models import (
    CompraDetalle,
    SalidaCamionDetalle,
    RetornoCamionDetalle,
    CanjeDescuentoDetalle,
    Producto,
)


def calcular_stock(producto_id):
    comprado = (
        db.session.query(func.coalesce(func.sum(CompraDetalle.cantidad_comprada_unidades), 0))
        .filter(CompraDetalle.producto_id == producto_id)
        .scalar()
    )
    salido = (
        db.session.query(func.coalesce(func.sum(SalidaCamionDetalle.cantidad_unidades), 0))
        .filter(SalidaCamionDetalle.producto_id == producto_id)
        .scalar()
    )
    regresado = (
        db.session.query(func.coalesce(func.sum(RetornoCamionDetalle.cantidad_unidades), 0))
        .filter(RetornoCamionDetalle.producto_id == producto_id)
        .scalar()
    )
    canjeado = (
        db.session.query(func.coalesce(func.sum(CanjeDescuentoDetalle.cantidad_unidades), 0))
        .filter(CanjeDescuentoDetalle.producto_id == producto_id)
        .scalar()
    )
    return comprado - salido + regresado + canjeado


def listar_stock_todos(solo_activos=True):
    """Devuelve una lista de dicts {producto, stock_unidades} para todos los productos."""
    query = Producto.query
    if solo_activos:
        query = query.filter_by(activo=True)
    productos = query.order_by(Producto.nombre).all()
    return [{"producto": p, "stock_unidades": calcular_stock(p.id)} for p in productos]


def stock_en_camion(salida_id):
    """Cuánto queda sin regresar de una salida específica (útil para precargar el retorno)."""
    from models import RetornoCamion

    salida_qty = (
        db.session.query(SalidaCamionDetalle.producto_id, SalidaCamionDetalle.cantidad_unidades)
        .filter(SalidaCamionDetalle.salida_id == salida_id)
        .all()
    )
    retorno = RetornoCamion.query.filter_by(salida_id=salida_id).first()
    regresado_por_producto = {}
    if retorno:
        for d in retorno.detalles:
            regresado_por_producto[d.producto_id] = d.cantidad_unidades
    return [
        {
            "producto_id": pid,
            "cantidad_salida": qty,
            "cantidad_regresada": regresado_por_producto.get(pid, 0),
        }
        for pid, qty in salida_qty
    ]
