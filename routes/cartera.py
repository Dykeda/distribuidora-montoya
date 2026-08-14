from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash

from extensions import db
from models import SalidaCamion, FacturaCartera, Cliente
from services.cartera import total_pendiente, facturas_con_antiguedad, resumen_antiguedad
from services.clientes import listar_clientes

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
    clientes = listar_clientes()
    salida_preseleccionada = request.args.get("salida_id", type=int)
    cliente_preseleccionado = request.args.get("cliente_id", type=int)

    if request.method == "POST":
        cliente_id = request.form.get("cliente_id")
        cliente = db.session.get(Cliente, int(cliente_id)) if cliente_id else None
        salida_id = request.form.get("salida_id")
        fecha_str = request.form.get("fecha")
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else date.today()
        except ValueError:
            fecha = date.today()

        errores = []
        if not cliente:
            errores.append("Debes elegir un cliente.")
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
                clientes=clientes,
                form=request.form,
                salida_preseleccionada=None,
                cliente_preseleccionado=None,
                hoy=date.today().isoformat(),
            )

        factura = FacturaCartera(
            salida_id=int(salida_id) if salida_id else None,
            cliente_id=cliente.id,
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
        clientes=clientes,
        form=None,
        salida_preseleccionada=salida_preseleccionada,
        cliente_preseleccionado=cliente_preseleccionado,
        hoy=date.today().isoformat(),
    )


@bp.route("/<int:factura_id>/marcar-pagada", methods=["POST"])
def marcar_pagada(factura_id):
    factura = FacturaCartera.query.get_or_404(factura_id)
    factura.estado = "pagada"
    factura.fecha_pago = date.today()
    db.session.commit()
    flash(f"Factura de {factura.cliente.nombre} marcada como pagada.", "success")
    return redirect(url_for("cartera.listar"))


@bp.route("/<int:factura_id>/marcar-pendiente", methods=["POST"])
def marcar_pendiente(factura_id):
    factura = FacturaCartera.query.get_or_404(factura_id)
    factura.estado = "pendiente"
    factura.fecha_pago = None
    db.session.commit()
    flash(f"Factura de {factura.cliente.nombre} marcada como pendiente de pago.", "success")
    return redirect(url_for("cartera.listar"))


@bp.route("/<int:factura_id>/eliminar", methods=["POST"])
def eliminar(factura_id):
    factura = FacturaCartera.query.get_or_404(factura_id)
    nombre_cliente = factura.cliente.nombre
    db.session.delete(factura)
    db.session.commit()
    flash(f"Factura de {nombre_cliente} eliminada.", "success")
    return redirect(url_for("cartera.listar"))
