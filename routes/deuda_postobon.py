import calendar
from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash

from extensions import db
from models import AjusteDeudaPostobon
from services.deuda_postobon import (
    deuda_postobon_a_la_fecha,
    movimientos_deuda,
    listar_ajustes_deuda,
)
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
    ajustes = listar_ajustes_deuda()

    return render_template(
        "deuda_postobon/index.html", anio=anio, mes=mes, meses=MESES_ES,
        deuda_actual=deuda_actual, deuda_fin_periodo=deuda_fin_periodo,
        movimientos=movimientos, ajustes=ajustes,
    )


@bp.route("/ajustes/nuevo", methods=["GET", "POST"])
def ajuste_nuevo():
    if request.method == "POST":
        fecha_str = request.form.get("fecha")
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else date.today()
        except ValueError:
            fecha = date.today()

        try:
            monto = int(round(float(request.form.get("monto") or 0)))
        except ValueError:
            monto = 0

        if monto == 0:
            flash("El monto no puede ser cero.", "error")
            return render_template(
                "deuda_postobon/ajuste_formulario.html", form=request.form,
                deuda_actual=deuda_postobon_a_la_fecha(date.today()),
            )

        db.session.add(AjusteDeudaPostobon(
            fecha=fecha, monto=monto, notas=request.form.get("notas") or None,
        ))
        db.session.commit()
        flash("Ajuste de deuda registrado.", "success")
        return redirect(url_for("deuda_postobon.index"))

    return render_template(
        "deuda_postobon/ajuste_formulario.html", form=None,
        deuda_actual=deuda_postobon_a_la_fecha(date.today()),
    )


@bp.route("/ajustes/<int:ajuste_id>/eliminar", methods=["POST"])
def ajuste_eliminar(ajuste_id):
    ajuste = AjusteDeudaPostobon.query.get_or_404(ajuste_id)
    db.session.delete(ajuste)
    db.session.commit()
    flash("Ajuste de deuda eliminado.", "success")
    return redirect(url_for("deuda_postobon.index"))
