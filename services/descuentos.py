from sqlalchemy import func

from extensions import db
from models import CompraDetalle, Compra, CanjeDescuentoDetalle, CanjeDescuento


def credito_generado_periodo(fecha_inicio, fecha_fin):
    total = (
        db.session.query(
            func.coalesce(
                func.sum(CompraDetalle.costo_linea * CompraDetalle.tasa_descuento_aplicada / 100.0),
                0,
            )
        )
        .join(Compra, CompraDetalle.compra_id == Compra.id)
        .filter(Compra.fecha >= fecha_inicio, Compra.fecha <= fecha_fin)
        .scalar()
    )
    return round(total)


def credito_canjeado_periodo(fecha_inicio, fecha_fin):
    total = (
        db.session.query(func.coalesce(func.sum(CanjeDescuentoDetalle.valor_usado), 0))
        .join(CanjeDescuento, CanjeDescuentoDetalle.canje_id == CanjeDescuento.id)
        .filter(CanjeDescuento.fecha >= fecha_inicio, CanjeDescuento.fecha <= fecha_fin)
        .scalar()
    )
    return round(total)


def credito_generado_total_hasta(fecha_corte):
    total = (
        db.session.query(
            func.coalesce(
                func.sum(CompraDetalle.costo_linea * CompraDetalle.tasa_descuento_aplicada / 100.0),
                0,
            )
        )
        .join(Compra, CompraDetalle.compra_id == Compra.id)
        .filter(Compra.fecha <= fecha_corte)
        .scalar()
    )
    return round(total)


def credito_canjeado_total_hasta(fecha_corte):
    total = (
        db.session.query(func.coalesce(func.sum(CanjeDescuentoDetalle.valor_usado), 0))
        .join(CanjeDescuento, CanjeDescuentoDetalle.canje_id == CanjeDescuento.id)
        .filter(CanjeDescuento.fecha <= fecha_corte)
        .scalar()
    )
    return round(total)


def saldo_acumulado(fecha_corte):
    return credito_generado_total_hasta(fecha_corte) - credito_canjeado_total_hasta(fecha_corte)
