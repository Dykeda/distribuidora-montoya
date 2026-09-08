import calendar
from datetime import date

from flask import Blueprint, render_template, request

from services.deuda_postobon import deuda_postobon_a_la_fecha, movimientos_deuda
from services.fechas import MESES_ES

bp = Blueprint("deuda_postobon", __name__, url_prefix="/deuda-postobon")


def _rango_mes(anio, mes):
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, 1), date(anio, mes, ultimo_dia)


@bp.route("/")
def index():
    hoy = date.today()
    anio = int(request.args.get("anio", hoy.year))
    mes = int(request.args.get("mes", hoy.month))
    fecha_inicio, fecha_fin = _rango_mes(anio, mes)

    deuda_actual = deuda_postobon_a_la_fecha(hoy)
    deuda_fin_periodo = deuda_postobon_a_la_fecha(fecha_fin)
    movimientos = movimientos_deuda(fecha_inicio, fecha_fin)

    return render_template(
        "deuda_postobon/index.html", anio=anio, mes=mes, meses=MESES_ES,
        deuda_actual=deuda_actual, deuda_fin_periodo=deuda_fin_periodo, movimientos=movimientos,
    )
