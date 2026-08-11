from sqlalchemy import func

from extensions import db
from models import CompraDetalle, Compra, CanjeDescuentoDetalle, CanjeDescuento, AjusteCredito, Producto


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


def ajustes_total_hasta(fecha_corte):
    total = (
        db.session.query(func.coalesce(func.sum(AjusteCredito.monto), 0))
        .filter(AjusteCredito.fecha <= fecha_corte)
        .scalar()
    )
    return round(total)


def listar_ajustes():
    return AjusteCredito.query.order_by(AjusteCredito.fecha.desc()).all()


def rendimiento_por_producto(fecha_inicio, fecha_fin):
    """Cuánto crédito de descuento generó cada producto en el período, de mayor a menor.
    Como la ganancia real del negocio es el crédito (no un margen de venta), esto le dice
    al dueño qué productos son los que más le convienen empujar, algo que no se ve solo
    mirando cuánto se vendió de cada uno."""
    filas = (
        db.session.query(
            Producto.nombre,
            func.coalesce(func.sum(CompraDetalle.costo_linea), 0).label("dinero_comprado"),
            func.coalesce(
                func.sum(CompraDetalle.costo_linea * CompraDetalle.tasa_descuento_aplicada / 100.0), 0
            ).label("credito_generado"),
        )
        .join(Compra, CompraDetalle.compra_id == Compra.id)
        .join(Producto, CompraDetalle.producto_id == Producto.id)
        .filter(Compra.fecha >= fecha_inicio, Compra.fecha <= fecha_fin)
        .group_by(Producto.id)
        .all()
    )

    resultado = []
    for nombre, dinero_comprado, credito_generado in filas:
        dinero_comprado = round(dinero_comprado)
        credito_generado = round(credito_generado)
        tasa_promedio = round(credito_generado / dinero_comprado * 100, 1) if dinero_comprado else 0.0
        resultado.append(
            {
                "producto": nombre,
                "dinero_comprado": dinero_comprado,
                "credito_generado": credito_generado,
                "tasa_promedio": tasa_promedio,
            }
        )
    resultado.sort(key=lambda f: f["credito_generado"], reverse=True)
    return resultado


def saldo_acumulado(fecha_corte):
    return (
        credito_generado_total_hasta(fecha_corte)
        + ajustes_total_hasta(fecha_corte)
        - credito_canjeado_total_hasta(fecha_corte)
    )
