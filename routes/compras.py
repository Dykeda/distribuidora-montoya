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
        filas.append({"compra": c, "costo_total": costo_total})
    return render_template("compras/lista.html", filas=filas)


@bp.route("/<int:compra_id>")
def detalle(compra_id):
    compra = Compra.query.get_or_404(compra_id)
    filas = []
    for d in compra.detalles:
        cajas, unidades_sueltas = cajas_y_unidades(d.producto, d.cantidad_comprada_unidades)
        filas.append({"detalle": d, "cajas": cajas, "unidades_sueltas": unidades_sueltas})

    costo_total = sum(d.costo_linea for d in compra.detalles)
    descuento_total = sum(d.costo_linea for d in compra.detalles if d.es_descuento)
    iva_total = sum(d.valor_iva for d in compra.detalles)
    total_a_pagar = costo_total + iva_total

    return render_template(
        "compras/detalle.html", compra=compra, filas=filas,
        costo_total=costo_total, descuento_total=descuento_total, iva_total=iva_total,
        total_a_pagar=total_a_pagar,
    )


@bp.route("/<int:compra_id>/eliminar", methods=["POST"])
def eliminar(compra_id):
    compra = Compra.query.get_or_404(compra_id)
    db.session.delete(compra)
    db.session.commit()
    flash("Compra eliminada. El inventario se recalcula solo.", "success")
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


@bp.route("/<int:compra_id>/linea/nueva", methods=["GET", "POST"])
def linea_nueva(compra_id):
    compra = Compra.query.get_or_404(compra_id)
    productos = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()

    if request.method == "POST":
        producto = db.session.get(Producto, int(request.form.get("producto_id") or 0))
        try:
            cajas = float(request.form.get("cajas") or 0)
            unidades = float(request.form.get("unidades") or 0)
            costo = int(request.form.get("costo_linea") or 0)
            tasa = float(request.form.get("tasa_descuento") or 0)
            iva = float(request.form.get("porcentaje_iva") or 0)
        except ValueError:
            producto = None
        es_descuento = bool(request.form.get("es_descuento"))

        if producto is None:
            flash("Selecciona un producto válido.", "error")
            return render_template("compras/linea_nueva_formulario.html", compra=compra, productos=productos, form=request.form)

        cantidad_unidades = round(cajas * producto.unidades_por_caja + unidades)
        if cantidad_unidades <= 0:
            flash("La cantidad debe ser mayor a cero.", "error")
            return render_template("compras/linea_nueva_formulario.html", compra=compra, productos=productos, form=request.form)

        compra.detalles.append(
            CompraDetalle(
                producto_id=producto.id,
                cantidad_comprada_unidades=cantidad_unidades,
                costo_linea=costo,
                tasa_descuento_aplicada=tasa,
                es_descuento=es_descuento,
                porcentaje_iva=iva,
            )
        )
        db.session.commit()
        flash("Producto agregado a la compra.", "success")
        return redirect(url_for("compras.detalle", compra_id=compra.id))

    return render_template("compras/linea_nueva_formulario.html", compra=compra, productos=productos, form=None)


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
            iva = float(request.form.get("porcentaje_iva") or 0)
        except ValueError:
            cajas = unidades = costo = tasa = iva = 0
        es_descuento = bool(request.form.get("es_descuento"))

        cantidad_unidades = round(cajas * producto.unidades_por_caja + unidades)
        if cantidad_unidades <= 0:
            flash("La cantidad debe ser mayor a cero.", "error")
        else:
            detalle.cantidad_comprada_unidades = cantidad_unidades
            detalle.costo_linea = costo
            detalle.tasa_descuento_aplicada = tasa
            detalle.es_descuento = es_descuento
            detalle.porcentaje_iva = iva
            db.session.commit()
            flash("Producto de la compra actualizado.", "success")
            return redirect(url_for("compras.detalle", compra_id=compra_id))

        return render_template(
            "compras/linea_formulario.html", compra=compra, detalle=detalle, producto=producto,
            cajas_actual=cajas, unidades_actual=unidades, es_descuento_actual=es_descuento, iva_actual=iva,
        )

    cajas_actual, unidades_actual = cajas_y_unidades(producto, detalle.cantidad_comprada_unidades)
    return render_template(
        "compras/linea_formulario.html", compra=compra, detalle=detalle, producto=producto,
        cajas_actual=cajas_actual, unidades_actual=unidades_actual, es_descuento_actual=detalle.es_descuento,
        iva_actual=detalle.porcentaje_iva,
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
        es_descuentos = request.form.getlist("es_descuento[]")
        ivas = request.form.getlist("porcentaje_iva[]")

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
                iva = float(ivas[i] or 0) if i < len(ivas) else 0.0
            except (ValueError, IndexError, TypeError):
                errores.append(f"Línea {i + 1}: datos inválidos.")
                continue
            es_descuento = i < len(es_descuentos) and es_descuentos[i] == "1"

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
                    es_descuento=es_descuento,
                    porcentaje_iva=iva,
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
