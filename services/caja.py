from extensions import db
from models import SalidaCamion, RetornoCamion, VentaBodega
from services.ventas import venta_por_salida
from services import gastos as gastos_service


def efectivo_por_salida(salida_id):
    """Efectivo real que trajo esa ruta: la venta implícita de la ruta, menos lo que quedó
    en cartera (no se cobró en efectivo, se lo llevó a deber el cliente). Devuelve None si
    la ruta todavía no tiene retorno registrado."""
    detalle = venta_por_salida(salida_id)
    if detalle is None:
        return None
    venta_total = sum(d["valor"] for d in detalle)
    salida = db.session.get(SalidaCamion, salida_id)
    cartera_generada = sum(f.monto for f in salida.facturas)
    return venta_total - cartera_generada


def entradas_en_periodo(fecha_inicio, fecha_fin):
    """Efectivo que entró en el período: rutas cerradas cuyo retorno cae en el período
    (venta - cartera) más venta directa en bodega (siempre en efectivo).
    fecha_inicio puede ser None para no poner límite inferior (todo hasta fecha_fin)."""
    total = 0

    retornos_q = RetornoCamion.query.filter(RetornoCamion.fecha <= fecha_fin)
    if fecha_inicio is not None:
        retornos_q = retornos_q.filter(RetornoCamion.fecha >= fecha_inicio)
    for retorno in retornos_q.all():
        efectivo = efectivo_por_salida(retorno.salida_id)
        if efectivo:
            total += efectivo

    bodega_q = VentaBodega.query.filter(VentaBodega.fecha <= fecha_fin)
    if fecha_inicio is not None:
        bodega_q = bodega_q.filter(VentaBodega.fecha >= fecha_inicio)
    for venta in bodega_q.all():
        total += sum(d.valor for d in venta.detalles)

    return total


def saldo_en_periodo(fecha_inicio, fecha_fin):
    """Efectivo neto del período: entradas (camión + bodega) menos salidas (gastos de
    negocio y de hogar, ver services/gastos.py)."""
    entradas = entradas_en_periodo(fecha_inicio, fecha_fin)
    salidas = gastos_service.total_gastos_periodo(fecha_inicio, fecha_fin)
    return entradas - salidas


def saldo_acumulado(fecha_corte):
    """Saldo de caja desde siempre hasta una fecha de corte: todas las entradas menos
    todas las salidas registradas hasta esa fecha."""
    return saldo_en_periodo(None, fecha_corte)


def historial_diario(fecha_inicio, fecha_fin):
    """Efectivo día por día en el período: entradas (camión/bodega) y salidas (gastos),
    con el neto de cada día."""
    por_fecha = {}

    def fila(fecha):
        return por_fecha.setdefault(fecha, {"camion": 0, "bodega": 0, "gastos": 0})

    retornos = RetornoCamion.query.filter(
        RetornoCamion.fecha >= fecha_inicio, RetornoCamion.fecha <= fecha_fin
    ).all()
    for retorno in retornos:
        efectivo = efectivo_por_salida(retorno.salida_id)
        if efectivo is None:
            continue
        fila(retorno.fecha)["camion"] += efectivo

    ventas_bodega = VentaBodega.query.filter(
        VentaBodega.fecha >= fecha_inicio, VentaBodega.fecha <= fecha_fin
    ).all()
    for venta in ventas_bodega:
        valor = sum(d.valor for d in venta.detalles)
        fila(venta.fecha)["bodega"] += valor

    gastos = gastos_service.listar_gastos()
    for g in gastos:
        if fecha_inicio <= g.fecha <= fecha_fin:
            fila(g.fecha)["gastos"] += g.monto

    filas = [
        {
            "fecha": fecha,
            "camion": v["camion"],
            "bodega": v["bodega"],
            "gastos": v["gastos"],
            "total": v["camion"] + v["bodega"] - v["gastos"],
        }
        for fecha, v in por_fecha.items()
    ]
    filas.sort(key=lambda f: f["fecha"], reverse=True)
    return filas
