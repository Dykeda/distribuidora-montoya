"""Deuda de dinero pendiente con Postobón (cuentas por pagar) -- distinto de "Faltantes
de descuento" (services/postobon.py), que lleva el % de descuento que Postobón no aplicó.
Cada factura de Postobón registrada a crédito (Compra.pago_contado=False) suma a la
deuda; cada pago por transferencia (Gasto de la categoría "Pago Postobón Transferencia")
la resta. Las facturas marcadas "pago de contado" nunca entran a la deuda -- se pagaron
en el momento, no hay nada que sumar ni luego restar.

Además, un AjusteDeudaPostobon (positivo o negativo) permite fijar a mano el saldo real
-- por ejemplo, para dejar la deuda en el valor verdadero cuando la suma automática de
todas las facturas a crédito quedó por encima de lo que de verdad se debe."""
from models import Compra, Gasto, CategoriaGasto, AjusteDeudaPostobon
from services.compras import total_a_pagar, es_postobon

NOMBRE_CATEGORIA_PAGO_TRANSFERENCIA = "Pago Postobón Transferencia"


def compras_a_credito(fecha_inicio, fecha_fin):
    """Compras de Postobón a crédito (no pagadas de contado) con fecha en el rango --
    fecha_inicio puede ser None para no poner límite inferior."""
    q = Compra.query.filter(Compra.fecha <= fecha_fin)
    if fecha_inicio is not None:
        q = q.filter(Compra.fecha >= fecha_inicio)
    return [c for c in q.all() if es_postobon(c) and not c.pago_contado]


def pagos_transferencia(fecha_inicio, fecha_fin):
    """Gasto de la categoría "Pago Postobón Transferencia" con fecha en el rango."""
    q = Gasto.query.join(CategoriaGasto).filter(
        CategoriaGasto.nombre == NOMBRE_CATEGORIA_PAGO_TRANSFERENCIA,
        Gasto.fecha <= fecha_fin,
    )
    if fecha_inicio is not None:
        q = q.filter(Gasto.fecha >= fecha_inicio)
    return q.order_by(Gasto.fecha.desc(), Gasto.id.desc()).all()


def ajustes_deuda(fecha_inicio, fecha_fin):
    """Ajustes manuales a la deuda con fecha en el rango -- fecha_inicio puede ser None
    para no poner límite inferior."""
    q = AjusteDeudaPostobon.query.filter(AjusteDeudaPostobon.fecha <= fecha_fin)
    if fecha_inicio is not None:
        q = q.filter(AjusteDeudaPostobon.fecha >= fecha_inicio)
    return q.order_by(AjusteDeudaPostobon.fecha.desc(), AjusteDeudaPostobon.id.desc()).all()


def listar_ajustes_deuda():
    """Todos los ajustes manuales, del más reciente al más antiguo (para mostrar y
    poder eliminar)."""
    return ajustes_deuda(None, _hoy_lejano())


def deuda_postobon_a_la_fecha(fecha_corte):
    """Deuda pendiente con Postobón desde siempre hasta una fecha de corte: todas las
    facturas a crédito, más los ajustes manuales, menos todos los pagos por transferencia
    registrados hasta esa fecha."""
    cargos = sum(total_a_pagar(c) for c in compras_a_credito(None, fecha_corte))
    ajustes = sum(a.monto for a in ajustes_deuda(None, fecha_corte))
    abonos = sum(g.monto for g in pagos_transferencia(None, fecha_corte))
    return cargos + ajustes - abonos


def movimientos_deuda(fecha_inicio, fecha_fin):
    """Cargos (facturas a crédito), ajustes manuales y abonos (pagos por transferencia)
    del período, ordenados por fecha con el saldo corrido -- para mostrar cómo se armó la
    deuda."""
    movimientos = []
    for c in compras_a_credito(fecha_inicio, fecha_fin):
        movimientos.append({
            "fecha": c.fecha, "tipo": "cargo",
            "descripcion": f"Factura {c.numero_factura}" if c.numero_factura else f"Compra #{c.id}",
            "monto": total_a_pagar(c), "compra_id": c.id,
        })
    for a in ajustes_deuda(fecha_inicio, fecha_fin):
        movimientos.append({
            "fecha": a.fecha, "tipo": "ajuste",
            "descripcion": a.notas or "Ajuste manual", "monto": a.monto, "ajuste_id": a.id,
        })
    for g in pagos_transferencia(fecha_inicio, fecha_fin):
        movimientos.append({
            "fecha": g.fecha, "tipo": "abono",
            "descripcion": g.notas or "Pago por transferencia", "monto": -g.monto, "gasto_id": g.id,
        })
    movimientos.sort(key=lambda m: (m["fecha"], m["tipo"]))

    saldo_previo = deuda_postobon_a_la_fecha(fecha_inicio - _un_dia()) if fecha_inicio else 0
    saldo = saldo_previo
    for m in movimientos:
        saldo += m["monto"]
        m["saldo"] = saldo

    movimientos.sort(key=lambda m: (m["fecha"], m["tipo"]), reverse=True)
    return movimientos


def _un_dia():
    from datetime import timedelta
    return timedelta(days=1)


def _hoy_lejano():
    from datetime import date
    return date(date.today().year + 100, 1, 1)
