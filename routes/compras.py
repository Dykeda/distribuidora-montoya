from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash

from extensions import db
from models import Producto, Compra, CompraDetalle
from services.inventario import cajas_y_unidades

bp = Blueprint("compras", __name__, url_prefix="/compras")


@bp.route("/")
def listar():
    compras = Compra.query.order_by(Compra.fecha.desc(), Compra.id.desc()).all()
    filas = []
    for c in compras:
        costo_total = sum(d.costo_linea for d in c.detalles)
        credito_total = sum(d.credito_generado for d in c.detalles)
        filas.append({"compra": c, "costo_total": costo_total, "credito_total": credito_total})
    return render_template("compras/lista.html", filas=filas)


@bp.route("/<int:compra_id>")
def detalle(compra_id):
    compra = Compra.query.get_or_404(compra_id)
    filas = []
    for d in compra.detalles:
        cajas, unidades_sueltas = cajas_y_unidades(d.producto, d.cantidad_comprada_unidades)
        filas.append({"detalle": d, "cajas": cajas, "unidades_sueltas": unidades_sueltas})
    return render_template("compras/detalle.html", compra=compra, filas=filas)


@bp.route("/<int:compra_id>/eliminar", methods=["POST"])
def eliminar(compra_id):
    compra = Compra.query.get_or_404(compra_id)
    db.session.delete(compra)
    db.session.commit()
    flash("Compra eliminada. El inventario y el crédito de descuento se recalculan solos.", "success")
    return redirect(url_for("compras.listar"))


@bp.route("/<int:compra_id>/linea/<int:detalle_id>/eliminar", methods=["POST"])
def linea_eliminar(compra_id, detalle_id):
    compra = Compra.query.get_or_404(compra_id)
    detalle = CompraDetalle.query.filter_by(id=detalle_id, compra_id=compra_id).first_or_404()
    db.session.delete(detalle)
    db.session.commit()

    if not compra.detalles:
        db.session.delete(compra)
        db.session.commit()
        flash("Producto eliminado. La compra se quedó sin productos, así que se eliminó por completo.", "success")
        return redirect(url_for("compras.listar"))

    flash("Producto eliminado de la compra.", "success")
    return redirect(url_for("compras.detalle", compra_id=compra_id))


@bp.route("/<int:compra_id>/linea/<int:detalle_id>/editar", methods=["GET", "POST"])
def linea_editar(compra_id, detalle_id):
    compra = Compra.query.get_or_404(compra_id)
    detalle = CompraDetalle.query.filter_by(id=detalle_id, compra_id=compra_id).first_or_404()
    producto = detalle.producto

    if request.method == "POST":
        try:
            cajas = float(request.form.get("cajas") or 0)
            unidades = float(request.form.get("unidades") or 0)
            costo = int(request.form.get("costo_linea") or 0)
            tasa = float(request.form.get("tasa_descuento") or 0)
        except ValueError:
            cajas = unidades = costo = tasa = 0

        cantidad_unidades = round(cajas * producto.unidades_por_caja + unidades)
        if cantidad_unidades <= 0:
            flash("La cantidad debe ser mayor a cero.", "error")
        else:
            detalle.cantidad_comprada_unidades = cantidad_unidades
            detalle.costo_linea = costo
            detalle.tasa_descuento_aplicada = tasa
            db.session.commit()
            flash("Producto de la compra actualizado.", "success")
            return redirect(url_for("compras.detalle", compra_id=compra_id))

        return render_template(
            "compras/linea_formulario.html", compra=compra, detalle=detalle, producto=producto,
            cajas_actual=cajas, unidades_actual=unidades,
        )

    cajas_actual, unidades_actual = cajas_y_unidades(producto, detalle.cantidad_comprada_unidades)
    return render_template(
        "compras/linea_formulario.html", compra=compra, detalle=detalle, producto=producto,
        cajas_actual=cajas_actual, unidades_actual=unidades_actual,
    )


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
        cajas_lista = request.form.getlist("cajas[]")
        unidades_lista = request.form.getlist("unidades[]")
        costos = request.form.getlist("costo_linea[]")
        tasas = request.form.getlist("tasa_descuento[]")

        lineas_validas = []
        errores = []
        for i, pid in enumerate(producto_ids):
            if not pid:
                continue
            try:
                producto = db.session.get(Producto, int(pid))
                cajas = float(cajas_lista[i] or 0)
                unidades = float(unidades_lista[i] or 0)
                costo = int(costos[i])
                tasa = float(tasas[i] or 0)
            except (ValueError, IndexError, TypeError):
                errores.append(f"Línea {i + 1}: datos inválidos.")
                continue

            if producto is None:
                errores.append(f"Línea {i + 1}: producto no encontrado.")
                continue

            cantidad_unidades = round(cajas * producto.unidades_por_caja + unidades)
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
