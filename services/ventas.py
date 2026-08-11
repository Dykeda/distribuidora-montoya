from extensions import db
from models import SalidaCamion, RetornoCamion, VentaBodega, Producto


def cargado_por_producto(salida):
    """Total cargado al camión para esta salida: carga inicial + todas las recargas del día."""
    cargado = {}
    for det in salida.detalles:
        cargado[det.producto_id] = cargado.get(det.producto_id, 0) + det.cantidad_unidades
    for recarga in salida.recargas:
        for det in recarga.detalles:
            cargado[det.producto_id] = cargado.get(det.producto_id, 0) + det.cantidad_unidades
    return cargado


def venta_por_salida(salida_id):
    """Detalle de venta implícita de una ruta cerrada: [{producto, cantidad_vendida, valor}, ...].
    "Cargado" incluye la salida inicial más cualquier recarga que se le haya mandado al
    camión en el día. Devuelve None si la salida no tiene retorno registrado (en tránsito)."""
    salida = db.session.get(SalidaCamion, salida_id)
    if salida is None or salida.retorno is None:
        return None

    retorno = salida.retorno
    cargado = cargado_por_producto(salida)
    regresado_por_producto = {d.producto_id: d.cantidad_unidades for d in retorno.detalles}

    resultado = []
    for producto_id, cantidad_cargada in cargado.items():
        producto = db.session.get(Producto, producto_id)
        cantidad_regresada = regresado_por_producto.get(producto_id, 0)
        cantidad_vendida = cantidad_cargada - cantidad_regresada
        precio = producto.precio_vigente(retorno.fecha) or 0
        resultado.append(
            {
                "producto": producto,
                "cantidad_vendida": cantidad_vendida,
                "precio_usado": precio,
                "valor": cantidad_vendida * precio,
            }
        )
    return resultado


def ventas_en_periodo(fecha_inicio, fecha_fin):
    """Valor total de venta del período: implícita de rutas cerradas (cuyo retorno cae en
    el período) más venta directa en bodega (cuya fecha cae en el período)."""
    total = 0
    detalle_por_producto = {}

    retornos = RetornoCamion.query.filter(
        RetornoCamion.fecha >= fecha_inicio, RetornoCamion.fecha <= fecha_fin
    ).all()
    for retorno in retornos:
        detalle = venta_por_salida(retorno.salida_id)
        if not detalle:
            continue
        for linea in detalle:
            total += linea["valor"]
            nombre = linea["producto"].nombre
            detalle_por_producto[nombre] = detalle_por_producto.get(nombre, 0) + linea["valor"]

    ventas_bodega = VentaBodega.query.filter(
        VentaBodega.fecha >= fecha_inicio, VentaBodega.fecha <= fecha_fin
    ).all()
    for venta in ventas_bodega:
        for d in venta.detalles:
            total += d.valor
            nombre = d.producto.nombre
            detalle_por_producto[nombre] = detalle_por_producto.get(nombre, 0) + d.valor

    return {"total": total, "por_producto": detalle_por_producto}


def rutas_en_transito():
    """Salidas de camión que todavía no tienen retorno registrado."""
    return (
        SalidaCamion.query.filter(~SalidaCamion.retorno.has())
        .order_by(SalidaCamion.fecha.desc())
        .all()
    )


def historial_diario(fecha_inicio, fecha_fin):
    """Venta bruta día por día (camión + bodega), ANTES de restar lo que quedó en
    cartera — a diferencia de Caja, que muestra el efectivo neto. Útil para ver cuánto se
    vendió en total cada día, sin importar si se cobró en efectivo o quedó a deber."""
    por_fecha = {}

    def fila(fecha):
        return por_fecha.setdefault(fecha, {"camion": 0, "bodega": 0})

    retornos = RetornoCamion.query.filter(
        RetornoCamion.fecha >= fecha_inicio, RetornoCamion.fecha <= fecha_fin
    ).all()
    for retorno in retornos:
        detalle = venta_por_salida(retorno.salida_id)
        if not detalle:
            continue
        fila(retorno.fecha)["camion"] += sum(d["valor"] for d in detalle)

    ventas_bodega = VentaBodega.query.filter(
        VentaBodega.fecha >= fecha_inicio, VentaBodega.fecha <= fecha_fin
    ).all()
    for venta in ventas_bodega:
        fila(venta.fecha)["bodega"] += sum(d.valor for d in venta.detalles)

    filas = [
        {"fecha": fecha, "camion": v["camion"], "bodega": v["bodega"], "total": v["camion"] + v["bodega"]}
        for fecha, v in por_fecha.items()
    ]
    filas.sort(key=lambda f: f["fecha"], reverse=True)
    return filas


def detalle_dia(fecha):
    """Todo lo que se vendió en una fecha específica: cada ruta de camión cerrada ese día
    (con su detalle por producto) y cada venta de bodega de ese día (con su detalle)."""
    rutas = []
    for retorno in RetornoCamion.query.filter(RetornoCamion.fecha == fecha).all():
        detalle = venta_por_salida(retorno.salida_id)
        if not detalle:
            continue
        rutas.append({"salida": retorno.salida, "detalle": detalle, "total": sum(d["valor"] for d in detalle)})

    ventas_bodega = []
    for venta in VentaBodega.query.filter(VentaBodega.fecha == fecha).all():
        ventas_bodega.append({"venta": venta, "total": sum(d.valor for d in venta.detalles)})

    return {"rutas": rutas, "ventas_bodega": ventas_bodega}
