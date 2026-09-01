import calendar
from datetime import date, datetime

from flask import Blueprint, render_template, request, abort

from services.ventas import historial_diario, detalle_dia, agrupar_por_semana
from services.fechas import MESES_ES

bp = Blueprint("venta_diaria", __name__, url_prefix="/venta-diaria")


@bp.route("/")
def listar():
    hoy = date.today()
    anio = int(request.args.get("anio", hoy.year))
    mes = int(request.args.get("mes", hoy.month))

    ultimo_dia = calendar.monthrange(anio, mes)[1]
    fecha_inicio, fecha_fin = date(anio, mes, 1), date(anio, mes, ultimo_dia)

    filas = historial_diario(fecha_inicio, fecha_fin)
    total_mes = sum(f["total"] for f in filas)
    camion_mes = sum(f["camion"] for f in filas)
    bodega_mes = sum(f["bodega"] for f in filas)
    semanas = agrupar_por_semana(filas)

    return render_template(
        "venta_diaria/lista.html",
        semanas=semanas,
        total_mes=total_mes,
        camion_mes=camion_mes,
        bodega_mes=bodega_mes,
        anio=anio,
        mes=mes,
        meses=MESES_ES,
    )


@bp.route("/<fecha_str>")
def detalle(fecha_str):
    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        abort(404)

    datos = detalle_dia(fecha)
    total = sum(r["total"] for r in datos["rutas"]) + sum(v["total"] for v in datos["ventas_bodega"])

    return render_template(
        "venta_diaria/detalle.html",
        fecha=fecha,
        rutas=datos["rutas"],
        ventas_bodega=datos["ventas_bodega"],
        total=total,
    )
