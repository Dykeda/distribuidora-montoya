from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash

from extensions import db
from models import SalidaCamion, FacturaCartera
from services.cartera import total_pendiente, facturas_con_antiguedad, resumen_antiguedad

bp = Blueprint("cartera", __name__, url_prefix="/cartera")


@bp.route("/")
def listar():
    return render_template(
        "cartera/lista.html",
        facturas=facturas_con_antiguedad(),
        total_pendiente=total_pendiente(),
        antiguedad=resumen_antiguedad(),
    )


@bp.route("/nueva", methods=["GET", "POST"])
def nueva():
    salidas = SalidaCamion.query.order_by(SalidaCamion.fecha.desc()).all()
    salida_preseleccionada = request.args.get("salida_id", type=int)

    if request.method == "POST":
        cliente = request.form.get("cliente", "").strip()
        salida_id = request.form.get("salida_id")
        fecha_str = request.form.get("fecha")
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else date.today()
        except ValueError:
            fecha = date.today()

        errores = []
        if not cliente:
            errores.append("El cliente es obligatorio.")
        try:
            monto = int(request.form.get("monto") or 0)
            if monto <= 0:
                raise ValueError
        except ValueError:
            monto = 0
            errores.append("El monto debe ser un número mayor a cero.")

        if errores:
            for e in errores:
                flash(e, "error")
            return render_template(
                "cartera/formulario.html",
                salidas=salidas,
                form=request.form,
                salida_preseleccionada=None,
                hoy=date.today().isoformat(),
            )

        factura = FacturaCartera(
            salida_id=int(salida_id) if salida_id else None,
            cliente=cliente,
            fecha=fecha,
            monto=monto,
            notas=request.form.get("notas") or None,
        )
        db.session.add(factura)
        db.session.commit()
        flash("Factura registrada en cartera.", "success")
        return redirect(url_for("cartera.listar"))

    return render_template(
        "cartera/formulario.html",
        salidas=salidas,
        form=None,
        salida_preseleccionada=salida_preseleccionada,
        hoy=date.today().isoformat(),
    )


@bp.route("/<int:factura_id>/marcar-pagada", methods=["POST"])
def marcar_pagada(factura_id):
    factura = FacturaCartera.query.get_or_404(factura_id)
    factura.estado = "pagada"
    factura.fecha_pago = date.today()
    db.session.commit()
    flash(f"Factura de {factura.cliente} marcada como pagada.", "success")
    return redirect(url_for("cartera.listar"))


@bp.route("/<int:factura_id>/marcar-pendiente", methods=["POST"])
def marcar_pendiente(factura_id):
    factura = FacturaCartera.query.get_or_404(factura_id)
    factura.estado = "pendiente"
    factura.fecha_pago = None
    db.session.commit()
    flash(f"Factura de {factura.cliente} marcada como pendiente de pago.", "success")
    return redirect(url_for("cartera.listar"))


@bp.route("/<int:factura_id>/eliminar", methods=["POST"])
def eliminar(factura_id):
    factura = FacturaCartera.query.get_or_404(factura_id)
    cliente = factura.cliente
    db.session.delete(factura)
    db.session.commit()
    flash(f"Factura de {cliente} eliminada.", "success")
    return redirect(url_for("cartera.listar"))
