import calendar
from datetime import date, datetime
from io import BytesIO

from flask import Blueprint, render_template, request, send_file

from services.descuentos import (
    listar_descuentos_agrupados,
    total_descuento_periodo,
    construir_workbook_descuentos,
)
from services.fechas import MESES_ES

bp = Blueprint("descuentos", __name__, url_prefix="/descuentos")


def _rango_mes(anio, mes):
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, 1), date(anio, mes, ultimo_dia)


@bp.route("/")
def listar():
    hoy = date.today()
    anio = int(request.args.get("anio", hoy.year))
    mes = int(request.args.get("mes", hoy.month))

    fecha_inicio, fecha_fin = _rango_mes(anio, mes)
    grupos = listar_descuentos_agrupados(fecha_inicio, fecha_fin)
    total = total_descuento_periodo(fecha_inicio, fecha_fin)

    return render_template(
        "descuentos/lista.html", grupos=grupos, total=total,
        anio=anio, mes=mes, meses=MESES_ES,
    )


@bp.route("/exportar-excel")
def exportar_excel():
    hoy = date.today()
    anio = int(request.args.get("anio", hoy.year))
    mes = int(request.args.get("mes", hoy.month))

    fecha_inicio, fecha_fin = _rango_mes(anio, mes)
    wb = construir_workbook_descuentos(fecha_inicio, fecha_fin)
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    marca = datetime.now().strftime("%Y-%m-%d_%H%M")
    nombre_archivo = f"descuentos_{anio}-{mes:02d}_{marca}.xlsx"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
