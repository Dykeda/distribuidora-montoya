import calendar
from datetime import date, datetime
from io import BytesIO

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file

from extensions import db
from models import Compra, AjustePostobon

from services.postobon import (
    listar_faltantes_agrupados,
    construir_workbook_faltantes,
    construir_workbook_faltantes_de_compra,
    listar_ajustes,
    total_pendiente_acumulado,
)
from services.fechas import MESES_ES

bp = Blueprint("postobon", __name__, url_prefix="/postobon")


def _rango_mes(anio, mes):
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, 1), date(anio, mes, ultimo_dia)


@bp.route("/")
def index():
    hoy = date.today()
    anio = int(request.args.get("anio", hoy.year))
    mes = int(request.args.get("mes", hoy.month))

    fecha_inicio, fecha_fin = _rango_mes(anio, mes)
    grupos = listar_faltantes_agrupados(fecha_inicio, fecha_fin)
    total_faltante = sum(g["subtotal"] for g in grupos)
    pendiente_acumulado = total_pendiente_acumulado()
    ajustes = listar_ajustes()

    return render_template(
        "postobon/informe.html", grupos=grupos, total_faltante=total_faltante,
        anio=anio, mes=mes, meses=MESES_ES,
        pendiente_acumulado=pendiente_acumulado, ajustes=ajustes,
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
            monto = int(request.form.get("monto") or 0)
        except ValueError:
            monto = 0

        if monto == 0:
            flash("El monto no puede ser cero.", "error")
            return render_template("postobon/ajuste_formulario.html", form=request.form)

        db.session.add(AjustePostobon(fecha=fecha, monto=monto, notas=request.form.get("notas") or None))
        db.session.commit()
        flash("Ajuste registrado.", "success")
        return redirect(url_for("postobon.index"))

    return render_template("postobon/ajuste_formulario.html", form=None)


@bp.route("/ajustes/<int:ajuste_id>/eliminar", methods=["POST"])
def ajuste_eliminar(ajuste_id):
    ajuste = AjustePostobon.query.get_or_404(ajuste_id)
    db.session.delete(ajuste)
    db.session.commit()
    flash("Ajuste eliminado.", "success")
    return redirect(url_for("postobon.index"))


@bp.route("/exportar-excel")
def exportar_excel():
    hoy = date.today()
    anio = int(request.args.get("anio", hoy.year))
    mes = int(request.args.get("mes", hoy.month))

    fecha_inicio, fecha_fin = _rango_mes(anio, mes)
    wb = construir_workbook_faltantes(fecha_inicio, fecha_fin)
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    marca = datetime.now().strftime("%Y-%m-%d_%H%M")
    nombre_archivo = f"faltantes_postobon_{anio}-{mes:02d}_{marca}.xlsx"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/exportar-excel/<int:compra_id>")
def exportar_excel_compra(compra_id):
    compra = Compra.query.get_or_404(compra_id)
    wb = construir_workbook_faltantes_de_compra(compra_id)
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    marca = datetime.now().strftime("%Y-%m-%d_%H%M")
    factura = compra.numero_factura or f"compra{compra.id}"
    nombre_archivo = f"faltantes_postobon_{factura}_{marca}.xlsx"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
