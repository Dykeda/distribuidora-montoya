"""Genera un Excel legible con toda la información del negocio, una hoja por tipo de
dato. Usado tanto por la descarga directa desde la web (routes/reportes.py) como por el
script de respaldo local (respaldo_local/generar_excel.py) — ahí es la única fuente de
esta lógica, para no mantenerla dos veces."""
from openpyxl import Workbook
from openpyxl.styles import Font

from models import (
    Producto,
    Compra,
    SalidaCamion,
    FacturaCartera,
    Gasto,
    CanjeDescuentoDetalle,
    AjusteCredito,
    VentaBodegaDetalle,
)
from services.ventas import cargado_por_producto


def _hoja(wb, nombre, encabezados, filas):
    ws = wb.create_sheet(nombre)
    ws.append(encabezados)
    for celda in ws[1]:
        celda.font = Font(bold=True)
    for fila in filas:
        ws.append(fila)
    for i, encabezado in enumerate(encabezados, start=1):
        ancho = max(len(str(encabezado)), 12)
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = ancho + 4


def construir_workbook():
    """Arma el Excel a partir de los datos actuales. Debe llamarse dentro de un
    contexto de aplicación Flask con acceso a la base de datos."""
    productos = Producto.query.order_by(Producto.nombre).all()

    wb = Workbook()
    wb.remove(wb.active)

    _hoja(
        wb, "Productos",
        ["Nombre", "Categoría", "Unidades/caja", "Precio actual (caja)", "Descuento ref. %", "Activo"],
        [
            [p.nombre, p.categoria or "", p.unidades_por_caja, p.precio_caja_actual() or 0,
             p.tasa_descuento_referencia, "Sí" if p.activo else "No"]
            for p in productos
        ],
    )

    compras = Compra.query.order_by(Compra.fecha.desc()).all()
    filas_compras = []
    for c in compras:
        for d in c.detalles:
            filas_compras.append([
                c.fecha, c.numero_factura or "", d.producto.nombre,
                d.cantidad_comprada_unidades, d.costo_linea, d.tasa_descuento_aplicada,
                d.credito_generado,
            ])
    _hoja(
        wb, "Compras",
        ["Fecha", "Factura", "Producto", "Cantidad (unid.)", "Costo", "Tasa descuento %", "Crédito generado"],
        filas_compras,
    )

    salidas = SalidaCamion.query.order_by(SalidaCamion.fecha.desc()).all()
    filas_salidas, filas_retornos = [], []
    for s in salidas:
        for pid, cant in cargado_por_producto(s).items():
            producto = next((p for p in productos if p.id == pid), None)
            filas_salidas.append([s.fecha, producto.nombre if producto else pid, cant])
        if s.retorno:
            for d in s.retorno.detalles:
                filas_retornos.append([s.fecha, s.retorno.fecha, d.producto.nombre, d.cantidad_unidades])
    _hoja(wb, "Camion Salidas", ["Fecha salida", "Producto", "Cantidad cargada (unid.)"], filas_salidas)
    _hoja(
        wb, "Camion Retornos",
        ["Fecha salida", "Fecha retorno", "Producto", "Cantidad regresada (unid.)"],
        filas_retornos,
    )

    facturas = FacturaCartera.query.order_by(FacturaCartera.fecha.desc()).all()
    _hoja(
        wb, "Cartera",
        ["Cliente", "Fecha factura", "Ruta (fecha salida)", "Monto", "Estado", "Fecha pago", "Notas"],
        [
            [f.cliente, f.fecha, f.salida.fecha if f.salida else "Deuda anterior",
             f.monto, f.estado, f.fecha_pago or "", f.notas or ""]
            for f in facturas
        ],
    )

    gastos = Gasto.query.order_by(Gasto.fecha.desc()).all()
    _hoja(
        wb, "Gastos",
        ["Fecha", "Categoría", "Tipo", "Monto", "Notas"],
        [[g.fecha, g.categoria.nombre, g.categoria.tipo, g.monto, g.notas or ""] for g in gastos],
    )

    canjes = CanjeDescuentoDetalle.query.all()
    _hoja(
        wb, "Descuentos Canjes",
        ["Fecha", "Producto", "Cantidad (unid.)", "Valor usado"],
        [[c.canje.fecha, c.producto.nombre, c.cantidad_unidades, c.valor_usado] for c in canjes],
    )

    ajustes = AjusteCredito.query.order_by(AjusteCredito.fecha.desc()).all()
    _hoja(
        wb, "Descuentos Ajustes",
        ["Fecha", "Monto", "Notas"],
        [[a.fecha, a.monto, a.notas or ""] for a in ajustes],
    )

    ventas_bodega = VentaBodegaDetalle.query.all()
    _hoja(
        wb, "Venta Bodega",
        ["Fecha", "Producto", "Cantidad (unid.)", "Valor"],
        [[v.venta.fecha, v.producto.nombre, v.cantidad_unidades, v.valor] for v in ventas_bodega],
    )

    return wb
