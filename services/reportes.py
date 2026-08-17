from sqlalchemy import func

from extensions import db
from models import CompraDetalle, Compra
from services import descuentos as descuentos_service
from services import ventas as ventas_service
from services import cartera as cartera_service
from services import caja as caja_service
from services import gastos as gastos_service


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
    descuento_contabilizado = descuentos_service.total_descuento_periodo(fecha_inicio, fecha_fin)
    cartera_pendiente = cartera_service.total_pendiente(fecha_fin)
    entradas_periodo = caja_service.entradas_en_periodo(fecha_inicio, fecha_fin)
    gastos_periodo = gastos_service.total_gastos_periodo(fecha_inicio, fecha_fin)
    saldo_caja_periodo = entradas_periodo - gastos_periodo
    saldo_caja_acumulado = caja_service.saldo_acumulado(fecha_fin)
    rendimiento_por_producto = descuentos_service.rendimiento_por_producto(fecha_inicio, fecha_fin)

    # Ganancia neta del negocio = descuento contabilizado - gastos de negocio (NO de
    # hogar, y NO la venta del camión/bodega — esa plata solo pasa por las manos del
    # negocio, se paga lo mismo a Postobón, no es ganancia real). Esta es una fórmula
    # provisional mientras se define la ganancia real (margen de venta vs. costo neto);
    # por ahora usa el mismo lugar donde antes iba el crédito de descuento.
    gastos_negocio_periodo = gastos_service.total_gastos_periodo(fecha_inicio, fecha_fin, tipo="negocio")
    ganancia_neta_periodo = descuento_contabilizado - gastos_negocio_periodo
    gastos_negocio_acumulado = gastos_service.total_gastos_periodo(None, fecha_fin, tipo="negocio")
    ganancia_neta_acumulada = descuentos_service.total_descuento_total_hasta(fecha_fin) - gastos_negocio_acumulado

    # % de descuento contabilizado del mes = descuento contabilizado / dinero comprado.
    if compra["dinero"] > 0:
        pct_descuento_promedio = round(descuento_contabilizado / compra["dinero"] * 100, 1)
    else:
        pct_descuento_promedio = 0.0

    return {
        "compra_total_dinero": compra["dinero"],
        "compra_total_unidades": compra["unidades"],
        "venta_total_dinero": venta["total"],
        "venta_por_producto": venta["por_producto"],
        "descuento_contabilizado": descuento_contabilizado,
        "cartera_pendiente": cartera_pendiente,
        "pct_descuento_promedio": pct_descuento_promedio,
        "entradas_periodo": entradas_periodo,
        "gastos_periodo": gastos_periodo,
        "saldo_caja_periodo": saldo_caja_periodo,
        "saldo_caja_acumulado": saldo_caja_acumulado,
        "rendimiento_por_producto": rendimiento_por_producto,
        "gastos_negocio_periodo": gastos_negocio_periodo,
        "ganancia_neta_periodo": ganancia_neta_periodo,
        "ganancia_neta_acumulada": ganancia_neta_acumulada,
    }
