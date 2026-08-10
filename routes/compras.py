from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash

from extensions import db
from models import Producto, Compra, CompraDetalle

bp = Blueprint("compras", __name__, url_prefix="/compras")


@bp.route("/")
def listar():
    compras = Compra.query.order_by(Compra.fecha.desc(), Compra.id.desc()).all()
    filas = []
    for c in compras:
        costo_total = sum(d.costo_linea for d in c.detalles)
        credito_total = sum(d.credito_generado for d in c.detalles)
        unidades_total = sum(d.cantidad_comprada_unidades for d in c.detalles)
        filas.append(
            {"compra": c, "costo_total": costo_total, "credito_total": credito_total, "unidades_total": unidades_total}
        )
    return render_template("compras/lista.html", filas=filas)


@bp.route("/<int:compra_id>")
def detalle(compra_id):
    compra = Compra.query.get_or_404(compra_id)
    return render_template("compras/detalle.html", compra=compra)


@bp.route("/nueva", methods=["GET", "POST"])
def nueva():
    productos = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()

    if request.method == "POST":
        fecha_str = request.form.get("fecha")
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else date.today()
        except ValueError:
            fecha = date.today()

        producto_ids = request.form.getlist("producto_id[]")
        cantidades = request.form.getlist("cantidad[]")
        tipos = request.form.getlist("tipo_cantidad[]")
        costos = request.form.getlist("costo_linea[]")
        tasas = request.form.getlist("tasa_descuento[]")

        lineas_validas = []
        errores = []
        for i, pid in enumerate(producto_ids):
            if not pid:
                continue
            try:
                producto = db.session.get(Producto, int(pid))
                cantidad = float(cantidades[i])
                tipo = tipos[i]
                costo = int(costos[i])
                tasa = float(tasas[i] or 0)
            except (ValueError, IndexError, TypeError):
                errores.append(f"Línea {i + 1}: datos inválidos.")
                continue

            if producto is None:
                errores.append(f"Línea {i + 1}: producto no encontrado.")
                continue

            factor = producto.unidades_por_caja if tipo == "caja" else 1
            cantidad_unidades = round(cantidad * factor)
            if cantidad_unidades <= 0:
                errores.append(f"Línea {i + 1}: la cantidad debe ser mayor a cero.")
                continue

            lineas_validas.append(
                CompraDetalle(
                    producto_id=producto.id,
                    cantidad_comprada_unidades=cantidad_unidades,
                    costo_linea=costo,
                    tasa_descuento_aplicada=tasa,
                )
            )

        if not lineas_validas:
            errores.append("Debes agregar al menos una línea de producto válida.")

        if errores:
            for e in errores:
                flash(e, "error")
            return render_template("compras/formulario.html", productos=productos, form=request.form)

        compra = Compra(
            fecha=fecha,
            numero_factura=request.form.get("numero_factura") or None,
            notas=request.form.get("notas") or None,
        )
        compra.detalles = lineas_validas
        db.session.add(compra)
        db.session.commit()
        flash("Compra registrada.", "success")
        return redirect(url_for("compras.listar"))

    return render_template("compras/formulario.html", productos=productos, form=None)
