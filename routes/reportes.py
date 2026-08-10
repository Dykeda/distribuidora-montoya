import calendar
from datetime import date

from flask import Blueprint, render_template, request

from services.reportes import resumen_periodo

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
        meses=list(calendar.month_name)[1:],
    )
