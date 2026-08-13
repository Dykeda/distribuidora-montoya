import calendar
from datetime import date
from io import BytesIO

from flask import Blueprint, render_template, request, send_file

from services.reportes import resumen_periodo
from services.fechas import MESES_ES
from services.exportar import construir_workbook

bp = Blueprint("reportes", __name__, url_prefix="/reportes")


def _rango_mes(anio, mes):
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, 1), date(anio, mes, ultimo_dia)


@bp.route("/")
def index():
    hoy = date.today()
    anio = int(request.args.get("anio", hoy.year))
    mes = int(request.args.get("mes", hoy.month))

    fecha_inicio, fecha_fin = _rango_mes(anio, mes)
    resumen = resumen_periodo(fecha_inicio, fecha_fin)

    return render_template(
        "reportes/mensual.html",
        resumen=resumen,
        anio=anio,
        mes=mes,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        meses=MESES_ES,
    )


@bp.route("/exportar-excel")
def exportar_excel():
    """Descarga toda la información del negocio en un Excel, una hoja por tipo de dato
    (Productos, Compras, Camión, Cartera, Gastos, Descuentos, Venta Bodega). Útil para
    tener una copia legible fuera del sistema sin necesitar nada técnico."""
    wb = construir_workbook()
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    nombre_archivo = f"distribuidora_montoya_{date.today().isoformat()}.xlsx"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
