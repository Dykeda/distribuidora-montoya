from sqlalchemy import func

from extensions import db
from models import CompraDetalle, Compra
from services import descuentos as descuentos_service
from services import ventas as ventas_service
from services import cartera as cartera_service


def compra_total_periodo(fecha_inicio, fecha_fin):
    dinero = (
        db.session.query(func.coalesce(func.sum(CompraDetalle.costo_linea), 0))
        .join(Compra, CompraDetalle.compra_id == Compra.id)
        .filter(Compra.fecha >= fecha_inicio, Compra.fecha <= fecha_fin)
        .scalar()
    )
    unidades = (
        db.session.query(func.coalesce(func.sum(CompraDetalle.cantidad_comprada_unidades), 0))
        .join(Compra, CompraDetalle.compra_id == Compra.id)
        .filter(Compra.fecha >= fecha_inicio, Compra.fecha <= fecha_fin)
        .scalar()
    )
    return {"dinero": round(dinero), "unidades": int(unidades)}


def resumen_periodo(fecha_inicio, fecha_fin):
    """Agrega todas las cifras clave de un período para las pantallas de Reportes/Dashboard."""
    compra = compra_total_periodo(fecha_inicio, fecha_fin)
    venta = ventas_service.ventas_en_periodo(fecha_inicio, fecha_fin)
    credito_generado = descuentos_service.credito_generado_periodo(fecha_inicio, fecha_fin)
    credito_canjeado = descuentos_service.credito_canjeado_periodo(fecha_inicio, fecha_fin)
    saldo = descuentos_service.saldo_acumulado(fecha_fin)
    cartera_pendiente = cartera_service.total_pendiente(fecha_fin)

    # % de descuento promedio del mes = crédito generado / dinero comprado, ponderado por
    # cuánto se compró de cada producto (no un promedio simple de las tasas ingresadas).
    if compra["dinero"] > 0:
        pct_descuento_promedio = round(credito_generado / compra["dinero"] * 100, 1)
    else:
        pct_descuento_promedio = 0.0

    return {
        "compra_total_dinero": compra["dinero"],
        "compra_total_unidades": compra["unidades"],
        "venta_total_dinero": venta["total"],
        "venta_por_producto": venta["por_producto"],
        "credito_generado": credito_generado,
        "credito_canjeado": credito_canjeado,
        "saldo_acumulado": saldo,
        "cartera_pendiente": cartera_pendiente,
        "pct_descuento_promedio": pct_descuento_promedio,
    }
