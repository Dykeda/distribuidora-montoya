from sqlalchemy import func

from extensions import db
from models import (
    CompraDetalle,
    SalidaCamionDetalle,
    RetornoCamionDetalle,
    RecargaCamionDetalle,
    VentaBodegaDetalle,
    PagoFaltantePostobonDetalle,
    Producto,
)


def _sumar(modelo, columna_cantidad, producto_id):
    return (
        db.session.query(func.coalesce(func.sum(columna_cantidad), 0))
        .filter(modelo.producto_id == producto_id)
        .scalar()
    )


def tiene_movimientos(producto_id):
    """True si el producto ya aparece en alguna compra, salida, recarga, retorno o venta
    de bodega. Un producto con movimientos reales no se puede eliminar (borrarlo
    corrompería el historial de esas transacciones) — solo desactivar. Uno sin ningún
    movimiento (ej. se creó por error) sí se puede eliminar de verdad."""
    modelos = [
        CompraDetalle,
        SalidaCamionDetalle,
        RetornoCamionDetalle,
        RecargaCamionDetalle,
        VentaBodegaDetalle,
        PagoFaltantePostobonDetalle,
    ]
    return any(modelo.query.filter_by(producto_id=producto_id).first() is not None for modelo in modelos)


def calcular_stock(producto_id):
    comprado = _sumar(CompraDetalle, CompraDetalle.cantidad_comprada_unidades, producto_id)
    salido = _sumar(SalidaCamionDetalle, SalidaCamionDetalle.cantidad_unidades, producto_id)
    recargado = _sumar(RecargaCamionDetalle, RecargaCamionDetalle.cantidad_unidades, producto_id)
    regresado = _sumar(RetornoCamionDetalle, RetornoCamionDetalle.cantidad_unidades, producto_id)
    vendido_bodega = _sumar(VentaBodegaDetalle, VentaBodegaDetalle.cantidad_unidades, producto_id)
    pagado_en_producto = _sumar(PagoFaltantePostobonDetalle, PagoFaltantePostobonDetalle.cantidad_unidades, producto_id)
    return comprado - salido - recargado + regresado - vendido_bodega + pagado_en_producto


def cajas_y_unidades(producto, stock):
    """Desglosa un stock en unidades en (cajas, unidades_sueltas), respetando si el
    producto realmente se maneja por cajas. Un producto con maneja_cajas=False (ej. bolsas
    de agua sueltas) no se empaca en cajas, así que todo el stock va como unidades sueltas
    aunque unidades_por_caja sea 1 — de lo contrario se vería como "cajas" por error."""
    if not producto.maneja_cajas:
        return 0, stock
    return stock // producto.unidades_por_caja, stock % producto.unidades_por_caja


def cajas_aproximadas(producto, cantidad_unidades):
    """Cajas redondeadas al entero más cercano, sin desglosar unidades sueltas -- para
    reportes donde un número aproximado de cajas es más útil que el desglose exacto.
    None si el producto no se maneja por cajas (ahí el llamador debe mostrar unidades)."""
    if not producto.maneja_cajas or not producto.unidades_por_caja:
        return None
    return round(cantidad_unidades / producto.unidades_por_caja)


def listar_stock_todos(solo_activos=True):
    """Devuelve una lista de dicts {producto, stock_unidades, cajas, unidades_sueltas}
    para todos los productos — cajas/unidades_sueltas es como el negocio piensa el stock,
    no en unidades sueltas totales."""
    query = Producto.query
    if solo_activos:
        query = query.filter_by(activo=True)
    productos = query.order_by(Producto.nombre).all()
    filas = []
    for p in productos:
        stock = calcular_stock(p.id)
        cajas, unidades_sueltas = cajas_y_unidades(p, stock)
        filas.append({
            "producto": p,
            "stock_unidades": stock,
            "cajas": cajas,
            "unidades_sueltas": unidades_sueltas,
        })
    return filas


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
