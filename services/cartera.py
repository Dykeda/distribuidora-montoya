from datetime import date

from sqlalchemy import func, or_

from extensions import db
from models import FacturaCartera, AbonoFactura, Cliente


def _saldo_a_fecha(factura, fecha_corte):
    """Saldo pendiente de una factura contando solo los abonos hechos hasta fecha_corte
    -- para que un reporte de un mes pasado muestre la cartera como estaba en ese momento,
    no como está hoy."""
    abonado = sum(a.monto for a in factura.abonos if a.fecha <= fecha_corte)
    return factura.monto - abonado


def total_pendiente(fecha_corte=None, cliente_id=None):
    """Dinero en cartera sin cobrar a la fecha de corte (hoy por defecto) -- ya descuenta
    los abonos parciales, no es el monto original de la factura. Incluye facturas
    todavía pendientes, y facturas que en esa fecha aún no se habían terminado de pagar
    (se pagaron después de fecha_corte). Con cliente_id, calcula el total pendiente de un
    solo cliente."""
    fecha_corte = fecha_corte or date.today()
    query = FacturaCartera.query.filter(FacturaCartera.fecha <= fecha_corte).filter(
        or_(
            FacturaCartera.estado == "pendiente",
            FacturaCartera.fecha_pago > fecha_corte,
        )
    )
    if cliente_id is not None:
        query = query.filter(FacturaCartera.cliente_id == cliente_id)
    return round(sum(max(_saldo_a_fecha(f, fecha_corte), 0) for f in query.all()))


def listar_facturas():
    return FacturaCartera.query.order_by(
        FacturaCartera.estado.desc(), FacturaCartera.fecha.desc()
    ).all()


def facturas_por_salida(salida_id):
    return (
        FacturaCartera.query.filter_by(salida_id=salida_id)
        .order_by(FacturaCartera.fecha.desc())
        .all()
    )


def listar_pendientes():
    """Facturas de cartera con saldo por cobrar (ya descontando abonos), con el cliente
    cargado -- para el buscador de "créditos pagados" del cuadre de caja de una ruta."""
    facturas = (
        FacturaCartera.query.filter_by(estado="pendiente")
        .join(Cliente)
        .order_by(Cliente.nombre, FacturaCartera.fecha)
        .all()
    )
    return [f for f in facturas if f.saldo_pendiente > 0]


def sincronizar_creditos_nuevos_en_ruta(retorno, salida, lineas):
    """Reemplaza todas las facturas de cartera que nacieron de este retorno (venta fiada
    ese día) con la lista nueva -- mismo patrón que sincronizar_gastos_en_ruta(). lineas es
    una lista de (cliente_id, monto, notas)."""
    FacturaCartera.query.filter_by(creada_en_retorno_id=retorno.id).delete()
    for cliente_id, monto, notas in lineas:
        if not cliente_id or not monto or monto <= 0:
            continue
        db.session.add(FacturaCartera(
            salida_id=salida.id, cliente_id=cliente_id, fecha=retorno.fecha, monto=monto,
            notas=notas or None, creada_en_retorno_id=retorno.id,
        ))


def _recalcular_estado(factura, fecha_si_pagada=None):
    """Marca la factura pagada sola cuando su saldo llega a 0 (o menos); si vuelve a
    quedar saldo (se quitó un abono), la regresa a pendiente. No toca facturas que un
    usuario haya forzado a "pagada" a mano sin abonos -- esta función solo se llama
    después de agregar/quitar un abono, nunca de forma general."""
    if factura.saldo_pendiente <= 0:
        factura.estado = "pagada"
        ultimo_abono = max((a.fecha for a in factura.abonos), default=fecha_si_pagada)
        factura.fecha_pago = ultimo_abono or fecha_si_pagada
    else:
        factura.estado = "pendiente"
        factura.fecha_pago = None


def registrar_abono(factura, fecha, monto, notas=None, retorno_id=None):
    """Agrega un abono (pago parcial o total) a una factura y recalcula su estado."""
    abono = AbonoFactura(factura_id=factura.id, fecha=fecha, monto=monto, notas=notas, retorno_id=retorno_id)
    db.session.add(abono)
    db.session.flush()
    # abonos puede haber quedado en caché de un cálculo anterior en esta misma sesión
    # (flush() no expira relaciones ya cargadas, solo commit() lo hace) -- se fuerza a
    # recargar para que _recalcular_estado vea el abono recién agregado.
    db.session.expire(factura, ["abonos"])
    _recalcular_estado(factura, fecha_si_pagada=fecha)
    return abono


def eliminar_abono(abono_id):
    abono = db.session.get(AbonoFactura, abono_id)
    if abono is None:
        return None
    factura = abono.factura
    db.session.delete(abono)
    db.session.flush()
    db.session.expire(factura, ["abonos"])
    _recalcular_estado(factura)
    return factura


def sincronizar_abonos_en_ruta(retorno, lineas):
    """Reemplaza todos los abonos que se registraron durante el cuadre de caja de esta
    ruta con la lista nueva -- mismo patrón que sincronizar_gastos_en_ruta(). lineas es una
    lista de (factura_id, monto). No toca abonos registrados a mano desde Cartera (esos no
    tienen retorno_id)."""
    abonos_existentes = AbonoFactura.query.filter_by(retorno_id=retorno.id).all()
    facturas_tocadas = {a.factura_id for a in abonos_existentes}
    for a in abonos_existentes:
        db.session.delete(a)

    for factura_id, monto in lineas:
        if not factura_id or not monto or monto <= 0:
            continue
        db.session.add(AbonoFactura(
            factura_id=factura_id, fecha=retorno.fecha, monto=monto, retorno_id=retorno.id,
        ))
        facturas_tocadas.add(factura_id)

    db.session.flush()
    for factura_id in facturas_tocadas:
        factura = db.session.get(FacturaCartera, factura_id)
        if factura is not None:
            db.session.expire(factura, ["abonos"])
            _recalcular_estado(factura, fecha_si_pagada=retorno.fecha)


def total_creditos_nuevos_en_ruta(retorno_id):
    total = (
        db.session.query(func.coalesce(func.sum(FacturaCartera.monto), 0))
        .filter(FacturaCartera.creada_en_retorno_id == retorno_id)
        .scalar()
    )
    return round(total)


def total_creditos_pagados_en_ruta(retorno_id):
    total = (
        db.session.query(func.coalesce(func.sum(AbonoFactura.monto), 0))
        .filter(AbonoFactura.retorno_id == retorno_id)
        .scalar()
    )
    return round(total)


RANGOS_ANTIGUEDAD = [
    {"etiqueta": "0-15 días", "min": 0, "max": 15},
    {"etiqueta": "16-30 días", "min": 16, "max": 30},
    {"etiqueta": "31-60 días", "min": 31, "max": 60},
    {"etiqueta": "Más de 60 días", "min": 61, "max": None},
]


def _rango_de(dias):
    for r in RANGOS_ANTIGUEDAD:
        if dias >= r["min"] and (r["max"] is None or dias <= r["max"]):
            return r["etiqueta"]
    return RANGOS_ANTIGUEDAD[-1]["etiqueta"]


def facturas_con_antiguedad(fecha_referencia=None):
    """Todas las facturas, con los días que lleva pendiente cada una sin cobrar (None para
    las ya pagadas). Útil para ver de un vistazo cuáles llevan más tiempo sin cobrarse."""
    fecha_referencia = fecha_referencia or date.today()
    resultado = []
    for f in listar_facturas():
        dias = (fecha_referencia - f.fecha).days if f.estado == "pendiente" else None
        resultado.append({"factura": f, "dias_pendiente": dias})
    return resultado


def resumen_antiguedad(fecha_referencia=None):
    """Agrupa el dinero pendiente por cobrar (ya con abonos descontados) en rangos de
    antigüedad (0-15, 16-30, 31-60, 60+ días). Con un margen tan ajustado, la cartera
    vieja es el riesgo más directo al flujo de caja — este resumen lo hace visible sin
    tener que revisar factura por factura."""
    fecha_referencia = fecha_referencia or date.today()
    rangos = {r["etiqueta"]: {"etiqueta": r["etiqueta"], "monto": 0, "cantidad": 0} for r in RANGOS_ANTIGUEDAD}

    pendientes = FacturaCartera.query.filter_by(estado="pendiente").all()
    for f in pendientes:
        dias = (fecha_referencia - f.fecha).days
        etiqueta = _rango_de(dias)
        rangos[etiqueta]["monto"] += max(f.saldo_pendiente, 0)
        rangos[etiqueta]["cantidad"] += 1

    return [rangos[r["etiqueta"]] for r in RANGOS_ANTIGUEDAD]
