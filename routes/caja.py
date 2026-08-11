import calendar
from datetime import date

from flask import Blueprint, render_template, request

from services.caja import efectivo_acumulado, historial_diario
from services.fechas import MESES_ES

bp = Blueprint("caja", __name__, url_prefix="/caja")


@bp.route("/")
def listar():
    hoy = date.today()
    anio = int(request.args.get("anio", hoy.year))
    mes = int(request.args.get("mes", hoy.month))

    ultimo_dia = calendar.monthrange(anio, mes)[1]
    fecha_inicio, fecha_fin = date(anio, mes, 1), date(anio, mes, ultimo_dia)

    filas = historial_diario(fecha_inicio, fecha_fin)
    total_mes = sum(f["total"] for f in filas)
    acumulado = efectivo_acumulado(date.today())

    return render_template(
        "caja/lista.html",
        filas=filas,
        total_mes=total_mes,
        acumulado=acumulado,
        anio=anio,
        mes=mes,
        meses=MESES_ES,
    )
