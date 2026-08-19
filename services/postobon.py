"""Detecta compras donde Postobón aplicó menos descuento del acordado por producto
(tasa_descuento_referencia), para poder reclamárselo."""
from openpyxl import Workbook
from openpyxl.styles import Font

from models import CompraDetalle, Compra, Producto


def listar_faltantes(fecha_inicio, fecha_fin):
    """Líneas de compra en el período donde el % de descuento aplicado fue menor al
    acordado por producto -- para reclamarle a Postobón. Solo considera compras con
    número de factura (una factura real de Postobón que se le puede reclamar) -- un
    ingreso de inventario físico sin factura (ej. un conteo de bodega) no aplica."""
    detalles = (
        CompraDetalle.query.join(Compra)
        .join(Producto)
        .filter(Compra.fecha >= fecha_inicio, Compra.fecha <= fecha_fin)
        .filter(Compra.numero_factura.isnot(None))
        .filter(CompraDetalle.es_descuento.is_(False))
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


def listar_faltantes_de_compra(compra_id):
    """Igual que listar_faltantes(), pero para una sola compra (factura) puntual."""
    detalles = (
        CompraDetalle.query.join(Compra)
        .join(Producto)
        .filter(Compra.id == compra_id)
        .filter(Compra.numero_factura.isnot(None))
        .filter(CompraDetalle.es_descuento.is_(False))
        .all()
    )
    filas = []
    for d in detalles:
        diferencia_pct = round(d.producto.tasa_descuento_referencia - d.tasa_descuento_aplicada, 1)
        if diferencia_pct <= 0:
            continue
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


def listar_faltantes_agrupados(fecha_inicio, fecha_fin):
    """Igual que listar_faltantes(), pero agrupado por factura -- cada grupo trae su
    propia lista de líneas y su subtotal, para que el informe no se vea suelto."""
    grupos_por_compra = {}
    for f in listar_faltantes(fecha_inicio, fecha_fin):
        compra = f["compra"]
        grupo = grupos_por_compra.setdefault(compra.id, {"compra": compra, "lineas": [], "subtotal": 0})
        grupo["lineas"].append(f)
        grupo["subtotal"] += f["monto_faltante"]

    grupos = list(grupos_por_compra.values())
    grupos.sort(key=lambda g: g["compra"].fecha, reverse=True)
    return grupos


def construir_workbook_faltantes(fecha_inicio, fecha_fin):
    wb = Workbook()
    ws = wb.active
    ws.title = "Faltantes de descuento"

    encabezados = ["Factura", "Fecha", "Producto", "Cantidad", "Costo", "% esperado", "% aplicado", "Diferencia %", "Monto faltante"]
    ws.append(encabezados)
    for celda in ws[1]:
        celda.font = Font(bold=True)

    total_general = 0
    for grupo in listar_faltantes_agrupados(fecha_inicio, fecha_fin):
        compra = grupo["compra"]
        for f in grupo["lineas"]:
            ws.append([
                compra.numero_factura, compra.fecha, f["producto"].nombre,
                f["detalle"].cantidad_comprada_unidades, f["detalle"].costo_linea,
                f["tasa_esperada"], f["tasa_aplicada"], f["diferencia_pct"], f["monto_faltante"],
            ])
        ws.append(["", "", "", "", "", "", "", "Subtotal factura", grupo["subtotal"]])
        for celda in ws[ws.max_row]:
            celda.font = Font(bold=True)
        total_general += grupo["subtotal"]

    ws.append(["", "", "", "", "", "", "", "TOTAL", total_general])
    for celda in ws[ws.max_row]:
        celda.font = Font(bold=True)

    for i, encabezado in enumerate(encabezados, start=1):
        ancho = max(len(str(encabezado)), 12)
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = ancho + 4

    return wb


def construir_workbook_faltantes_de_compra(compra_id):
    wb = Workbook()
    ws = wb.active
    ws.title = "Faltantes de descuento"

    encabezados = ["Factura", "Fecha", "Producto", "Cantidad", "Costo", "% esperado", "% aplicado", "Diferencia %", "Monto faltante"]
    ws.append(encabezados)
    for celda in ws[1]:
        celda.font = Font(bold=True)

    filas = listar_faltantes_de_compra(compra_id)
    total = 0
    for f in filas:
        compra = f["compra"]
        ws.append([
            compra.numero_factura, compra.fecha, f["producto"].nombre,
            f["detalle"].cantidad_comprada_unidades, f["detalle"].costo_linea,
            f["tasa_esperada"], f["tasa_aplicada"], f["diferencia_pct"], f["monto_faltante"],
        ])
        total += f["monto_faltante"]

    ws.append(["", "", "", "", "", "", "", "TOTAL", total])
    for celda in ws[ws.max_row]:
        celda.font = Font(bold=True)

    for i, encabezado in enumerate(encabezados, start=1):
        ancho = max(len(str(encabezado)), 12)
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = ancho + 4

    return wb
