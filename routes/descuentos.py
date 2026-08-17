from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash

from extensions import db
from models import Producto, CanjeDescuento, CanjeDescuentoDetalle, AjusteCredito
from services.descuentos import saldo_acumulado, listar_ajustes
from services.inventario import cajas_y_unidades

bp = Blueprint("descuentos", __name__, url_prefix="/descuentos")


@bp.route("/")
def listar():
    canjes = CanjeDescuento.query.order_by(CanjeDescuento.fecha.desc(), CanjeDescuento.id.desc()).all()
    filas = [{"canje": c, "valor_total": sum(d.valor_usado for d in c.detalles)} for c in canjes]
    saldo = saldo_acumulado(date.today())
    return render_template(
        "descuentos/lista.html", filas=filas, saldo=saldo, ajustes=listar_ajustes()
    )


@bp.route("/ajuste/nuevo", methods=["GET", "POST"])
def ajuste_nuevo():
    if request.method == "POST":
        fecha_str = request.form.get("fecha")
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else date.today()
        except ValueError:
            fecha = date.today()

        try:
            monto = int(request.form.get("monto") or 0)
            if monto == 0:
                raise ValueError
        except ValueError:
            flash("El monto debe ser un número distinto de cero.", "error")
            return render_template("descuentos/ajuste_formulario.html", form=request.form)

        ajuste = AjusteCredito(fecha=fecha, monto=monto, notas=request.form.get("notas") or None)
        db.session.add(ajuste)
        db.session.commit()
        flash("Ajuste de crédito registrado.", "success")
        return redirect(url_for("descuentos.listar"))

    return render_template("descuentos/ajuste_formulario.html", form=None)


@bp.route("/canje/nuevo", methods=["GET", "POST"])
def canje_nuevo():
    productos = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()
    producto_por_id = {p.id: p for p in productos}
    saldo = saldo_acumulado(date.today())

    if request.method == "POST":
        fecha_str = request.form.get("fecha")
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else date.today()
        except ValueError:
            fecha = date.today()

        producto_ids = request.form.getlist("producto_id[]")
        cantidades = request.form.getlist("cantidad[]")
        tipos = request.form.getlist("tipo_cantidad[]")

        lineas, errores = [], []
        for i, pid in enumerate(producto_ids):
            if not pid:
                continue
            try:
                producto = producto_por_id.get(int(pid))
                cantidad = float(cantidades[i])
                tipo = tipos[i]
            except (ValueError, IndexError, TypeError):
                errores.append(f"Línea {i + 1}: datos inválidos.")
                continue
            if producto is None:
                errores.append(f"Línea {i + 1}: producto no encontrado.")
                continue

            precio = producto.precio_vigente(fecha)
            if precio is None:
                errores.append(f"{producto.nombre}: no tiene precio definido.")
                continue

            factor = producto.unidades_por_caja if tipo == "caja" else 1
            cantidad_unidades = round(cantidad * factor)
            if cantidad_unidades <= 0:
                errores.append(f"Línea {i + 1}: la cantidad debe ser mayor a cero.")
                continue

            lineas.append(
                CanjeDescuentoDetalle(
                    producto_id=producto.id,
                    cantidad_unidades=cantidad_unidades,
                    valor_usado=cantidad_unidades * precio,
                )
            )

        if not lineas:
            errores.append("Debes agregar al menos un producto a canjear.")

        if errores:
            for e in errores:
                flash(e, "error")
            return render_template(
                "descuentos/canje_formulario.html", productos=productos, form=request.form, saldo=saldo
            )

        valor_total = sum(d.valor_usado for d in lineas)
        if valor_total > saldo:
            flash(
                f"Aviso: este canje (${valor_total:,}) supera el saldo disponible (${saldo:,}). Se guardó de todas formas.",
                "warning",
            )

        canje = CanjeDescuento(fecha=fecha, notas=request.form.get("notas") or None)
        canje.detalles = lineas
        db.session.add(canje)
        db.session.commit()
        flash("Canje registrado. Inventario y saldo actualizados.", "success")
        return redirect(url_for("descuentos.listar"))

    return render_template("descuentos/canje_formulario.html", productos=productos, form=None, saldo=saldo)


@bp.route("/canje/<int:canje_id>")
def canje_detalle(canje_id):
    canje = CanjeDescuento.query.get_or_404(canje_id)
    filas = []
    for d in canje.detalles:
        cajas, unidades_sueltas = cajas_y_unidades(d.producto, d.cantidad_unidades)
        filas.append({"detalle": d, "cajas": cajas, "unidades_sueltas": unidades_sueltas})
    return render_template("descuentos/canje_detalle.html", canje=canje, filas=filas)


@bp.route("/canje/<int:canje_id>/eliminar", methods=["POST"])
def canje_eliminar(canje_id):
    canje = CanjeDescuento.query.get_or_404(canje_id)
    db.session.delete(canje)
    db.session.commit()
    flash("Canje eliminado. El inventario y el saldo de crédito se recalculan solos.", "success")
    return redirect(url_for("descuentos.listar"))


@bp.route("/canje/<int:canje_id>/linea/<int:detalle_id>/eliminar", methods=["POST"])
def canje_linea_eliminar(canje_id, detalle_id):
    canje = CanjeDescuento.query.get_or_404(canje_id)
    detalle = CanjeDescuentoDetalle.query.filter_by(id=detalle_id, canje_id=canje_id).first_or_404()
    db.session.delete(detalle)
    db.session.commit()

    if not canje.detalles:
        db.session.delete(canje)
        db.session.commit()
        flash("Producto eliminado. El canje se quedó sin productos, así que se eliminó por completo.", "success")
        return redirect(url_for("descuentos.listar"))

    flash("Producto eliminado del canje.", "success")
    return redirect(url_for("descuentos.canje_detalle", canje_id=canje_id))


@bp.route("/canje/<int:canje_id>/linea/<int:detalle_id>/editar", methods=["GET", "POST"])
def canje_linea_editar(canje_id, detalle_id):
    canje = CanjeDescuento.query.get_or_404(canje_id)
    detalle = CanjeDescuentoDetalle.query.filter_by(id=detalle_id, canje_id=canje_id).first_or_404()
    producto = detalle.producto

    if request.method == "POST":
        try:
            cajas = float(request.form.get("cajas") or 0)
            unidades = float(request.form.get("unidades") or 0)
        except ValueError:
            cajas = unidades = 0

        cantidad_unidades = round(cajas * producto.unidades_por_caja + unidades)
        precio = producto.precio_vigente(canje.fecha)

        if cantidad_unidades <= 0:
            flash("La cantidad debe ser mayor a cero.", "error")
        elif precio is None:
            flash(f"{producto.nombre}: no tiene precio definido para la fecha del canje.", "error")
        else:
            detalle.cantidad_unidades = cantidad_unidades
            detalle.valor_usado = cantidad_unidades * precio
            db.session.commit()
            flash("Producto del canje actualizado.", "success")
            return redirect(url_for("descuentos.canje_detalle", canje_id=canje_id))

        return render_template(
            "descuentos/canje_linea_formulario.html", canje=canje, detalle=detalle, producto=producto,
            cajas_actual=cajas, unidades_actual=unidades,
        )

    cajas_actual, unidades_actual = cajas_y_unidades(producto, detalle.cantidad_unidades)
    return render_template(
        "descuentos/canje_linea_formulario.html", canje=canje, detalle=detalle, producto=producto,
        cajas_actual=cajas_actual, unidades_actual=unidades_actual,
    )
