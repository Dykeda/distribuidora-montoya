import calendar
from datetime import date, datetime
from io import BytesIO

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file

from extensions import db
from models import Compra, AjustePostobon, Producto, PagoFaltantePostobon, PagoFaltantePostobonDetalle

from services.postobon import (
    listar_faltantes_agrupados,
    construir_workbook_faltantes,
    construir_workbook_faltantes_de_compra,
    listar_ajustes,
    listar_pagos_faltante,
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
    pagos = listar_pagos_faltante()

    return render_template(
        "postobon/informe.html", grupos=grupos, total_faltante=total_faltante,
        anio=anio, mes=mes, meses=MESES_ES,
        pendiente_acumulado=pendiente_acumulado, ajustes=ajustes, pagos=pagos,
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


@bp.route("/pagos/nuevo", methods=["GET", "POST"])
def pago_nuevo():
    productos = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()

    if request.method == "POST":
        fecha_str = request.form.get("fecha")
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else date.today()
        except ValueError:
            fecha = date.today()

        producto_ids = request.form.getlist("producto_id[]")
        cajas_lista = request.form.getlist("cajas[]")
        unidades_lista = request.form.getlist("unidades[]")

        errores = []
        lineas = []
        for i, pid in enumerate(producto_ids):
            if not pid:
                continue
            try:
                producto = db.session.get(Producto, int(pid))
                cajas = float(cajas_lista[i] or 0)
                unidades = float(unidades_lista[i] or 0)
            except (ValueError, IndexError, TypeError):
                errores.append(f"Línea {i + 1}: datos inválidos.")
                continue
            if producto is None:
                errores.append(f"Línea {i + 1}: producto no encontrado.")
                continue
            cantidad = round(cajas * producto.unidades_por_caja + unidades)
            if cantidad <= 0:
                errores.append(f"Línea {i + 1}: la cantidad debe ser mayor a cero.")
                continue
            valor = round(cantidad * (producto.precio_actual() or 0))
            lineas.append(PagoFaltantePostobonDetalle(
                producto_id=producto.id, cantidad_unidades=cantidad, valor=valor,
            ))

        if not lineas:
            errores.append("Debes agregar al menos una línea de producto válida.")

        if errores:
            for e in errores:
                flash(e, "error")
            return render_template("postobon/pago_formulario.html", productos=productos, form=request.form)

        pago = PagoFaltantePostobon(fecha=fecha, notas=request.form.get("notas") or None)
        pago.detalles = lineas
        db.session.add(pago)
        db.session.commit()
        flash("Pago de faltante registrado.", "success")
        return redirect(url_for("postobon.index"))

    return render_template("postobon/pago_formulario.html", productos=productos, form=None)


@bp.route("/pagos/<int:pago_id>/eliminar", methods=["POST"])
def pago_eliminar(pago_id):
    pago = PagoFaltantePostobon.query.get_or_404(pago_id)
    db.session.delete(pago)
    db.session.commit()
    flash("Pago eliminado.", "success")
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
