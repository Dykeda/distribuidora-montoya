from extensions import db
from models import SalidaCamion, RetornoCamion, SalidaCamionDetalle, Producto


def venta_por_salida(salida_id):
    """Detalle de venta implícita de una ruta cerrada: [{producto, cantidad_vendida, valor}, ...].
    Devuelve None si la salida no tiene retorno registrado (sigue en tránsito)."""
    salida = db.session.get(SalidaCamion, salida_id)
    if salida is None or salida.retorno is None:
        return None

    retorno = salida.retorno
    regresado_por_producto = {d.producto_id: d.cantidad_unidades for d in retorno.detalles}

    resultado = []
    for det in salida.detalles:
        cantidad_regresada = regresado_por_producto.get(det.producto_id, 0)
        cantidad_vendida = det.cantidad_unidades - cantidad_regresada
        precio = det.producto.precio_vigente(retorno.fecha) or 0
        resultado.append(
            {
                "producto": det.producto,
                "cantidad_vendida": cantidad_vendida,
                "precio_usado": precio,
                "valor": cantidad_vendida * precio,
            }
        )
    return resultado


def ventas_en_periodo(fecha_inicio, fecha_fin):
    """Valor total de ventas implícitas de rutas cerradas cuyo retorno cae en el período."""
    retornos = RetornoCamion.query.filter(
        RetornoCamion.fecha >= fecha_inicio, RetornoCamion.fecha <= fecha_fin
    ).all()

    total = 0
    detalle_por_producto = {}
    for retorno in retornos:
        detalle = venta_por_salida(retorno.salida_id)
        if not detalle:
            continue
        for linea in detalle:
            total += linea["valor"]
            nombre = linea["producto"].nombre
            detalle_por_producto[nombre] = detalle_por_producto.get(nombre, 0) + linea["valor"]

    return {"total": total, "por_producto": detalle_por_producto}


def rutas_en_transito():
    """Salidas de camión que todavía no tienen retorno registrado."""
    return (
        SalidaCamion.query.filter(~SalidaCamion.retorno.has())
        .order_by(SalidaCamion.fecha.desc())
        .all()
    )
