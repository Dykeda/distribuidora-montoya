"""Detecta compras donde Postobón aplicó menos descuento del acordado por producto
(tasa_descuento_referencia), para poder reclamárselo."""
from openpyxl import Workbook

from models import CompraDetalle, Compra, Producto
from services.exportar import _hoja


def listar_faltantes(fecha_inicio, fecha_fin):
    """Líneas de compra en el período donde el % de descuento aplicado fue menor al
    acordado por producto -- para reclamarle a Postobón."""
    detalles = (
        CompraDetalle.query.join(Compra)
        .join(Producto)
        .filter(Compra.fecha >= fecha_inicio, Compra.fecha <= fecha_fin)
        .order_by(Compra.fecha.desc())
        .all()
    )
    filas = []
    for d in detalles:
        diferencia_pct = round(d.producto.tasa_descuento_referencia - d.tasa_descuento_aplicada, 1)
        if diferencia_pct <= 0:
            continue  # sin faltante, o aplicó igual o más de lo esperado
        monto_faltante = round(d.costo_linea * diferencia_pct / 100)
        filas.append({
            "compra": d.compra,
            "detalle": d,
            "producto": d.producto,
            "tasa_esperada": d.producto.tasa_descuento_referencia,
            "tasa_aplicada": d.tasa_descuento_aplicada,
            "diferencia_pct": diferencia_pct,
            "monto_faltante": monto_faltante,
        })
    return filas


def construir_workbook_faltantes(fecha_inicio, fecha_fin):
    wb = Workbook()
    wb.remove(wb.active)
    _hoja(
        wb, "Faltantes de descuento",
        ["Fecha compra", "Producto", "Cantidad", "Costo", "% esperado", "% aplicado", "Diferencia %", "Monto faltante"],
        [
            [
                f["compra"].fecha, f["producto"].nombre, f["detalle"].cantidad_comprada_unidades,
                f["detalle"].costo_linea, f["tasa_esperada"], f["tasa_aplicada"],
                f["diferencia_pct"], f["monto_faltante"],
            ]
            for f in listar_faltantes(fecha_inicio, fecha_fin)
        ],
    )
    return wb
