from datetime import timedelta

from extensions import db
from models import SalidaCamion, RetornoCamion, VentaBodega, Producto
from services.inventario import cajas_aproximadas


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
    el período) más venta directa en bodega (cuya fecha cae en el período). por_producto
    trae, para cada producto, cuántas cajas físicas se vendieron (redondeado, sin desglose
    de unidades sueltas) y el valor en dinero -- ordenado de mayor a menor valor vendido
    (el más exitoso primero)."""
    total = 0
    detalle_por_producto = {}

    def _fila(producto):
        return detalle_por_producto.setdefault(
            producto.id, {"producto": producto, "cantidad_unidades": 0, "valor": 0}
        )

    retornos = RetornoCamion.query.filter(
        RetornoCamion.fecha >= fecha_inicio, RetornoCamion.fecha <= fecha_fin
    ).all()
    for retorno in retornos:
        detalle = venta_por_salida(retorno.salida_id)
        if not detalle:
            continue
        for linea in detalle:
            total += linea["valor"]
            fila = _fila(linea["producto"])
            fila["cantidad_unidades"] += linea["cantidad_vendida"]
            fila["valor"] += linea["valor"]

    ventas_bodega = VentaBodega.query.filter(
        VentaBodega.fecha >= fecha_inicio, VentaBodega.fecha <= fecha_fin
    ).all()
    for venta in ventas_bodega:
        for d in venta.detalles:
            total += d.valor
            fila = _fila(d.producto)
            fila["cantidad_unidades"] += d.cantidad_unidades
            fila["valor"] += d.valor

    por_producto = []
    for fila in detalle_por_producto.values():
        por_producto.append({
            "producto": fila["producto"],
            "cantidad_unidades": fila["cantidad_unidades"],
            "cajas": cajas_aproximadas(fila["producto"], fila["cantidad_unidades"]),
            "valor": fila["valor"],
        })
    por_producto.sort(key=lambda f: f["valor"], reverse=True)

    return {"total": total, "por_producto": por_producto}


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


def agrupar_por_semana(filas):
    """Agrupa las filas de historial_diario (ya ordenadas por fecha, más reciente
    primero) en semanas calendario (lunes a domingo), cada una con su propio subtotal --
    para ver de un vistazo cuánto se vendió en la semana sin sumar los días a mano. Solo
    agrupa los días que ya vienen en filas (con venta real), no rellena días vacíos."""
    grupos = []
    semana_actual = None
    grupo_actual = None
    for f in filas:
        lunes = f["fecha"] - timedelta(days=f["fecha"].weekday())
        if lunes != semana_actual:
            grupo_actual = {
                "inicio": lunes, "fin": lunes + timedelta(days=6),
                "dias": [], "camion": 0, "bodega": 0, "total": 0,
            }
            grupos.append(grupo_actual)
            semana_actual = lunes
        grupo_actual["dias"].append(f)
        grupo_actual["camion"] += f["camion"]
        grupo_actual["bodega"] += f["bodega"]
        grupo_actual["total"] += f["total"]
    return grupos


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
