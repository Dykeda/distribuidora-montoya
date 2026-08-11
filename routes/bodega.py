from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash

from extensions import db
from models import Producto, VentaBodega, VentaBodegaDetalle

bp = Blueprint("bodega", __name__, url_prefix="/bodega")


@bp.route("/")
def listar():
    ventas = VentaBodega.query.order_by(VentaBodega.fecha.desc(), VentaBodega.id.desc()).all()
    filas = [{"venta": v, "valor_total": sum(d.valor for d in v.detalles)} for v in ventas]
    return render_template("bodega/lista.html", filas=filas)


@bp.route("/nueva", methods=["GET", "POST"])
def nueva():
    productos = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()
    producto_por_id = {p.id: p for p in productos}

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
                VentaBodegaDetalle(
                    producto_id=producto.id,
                    cantidad_unidades=cantidad_unidades,
                    valor=cantidad_unidades * precio,
                )
            )

        if not lineas:
            errores.append("Debes agregar al menos un producto vendido.")

        if errores:
            for e in errores:
                flash(e, "error")
            return render_template("bodega/formulario.html", productos=productos, form=request.form)

        venta = VentaBodega(fecha=fecha, notas=request.form.get("notas") or None)
        venta.detalles = lineas
        db.session.add(venta)
        db.session.commit()
        flash("Venta en bodega registrada. Inventario actualizado.", "success")
        return redirect(url_for("bodega.listar"))

    return render_template("bodega/formulario.html", productos=productos, form=None)
