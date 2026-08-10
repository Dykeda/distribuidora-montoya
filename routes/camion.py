from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash

from extensions import db
from models import Producto, SalidaCamion, SalidaCamionDetalle, RetornoCamion, RetornoCamionDetalle
from services.ventas import venta_por_salida, rutas_en_transito

bp = Blueprint("camion", __name__, url_prefix="/camion")


def _parsear_fecha(nombre_campo):
    fecha_str = request.form.get(nombre_campo)
    try:
        return datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else date.today()
    except ValueError:
        return date.today()


def _parsear_lineas(producto_por_id):
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
        factor = producto.unidades_por_caja if tipo == "caja" else 1
        cantidad_unidades = round(cantidad * factor)
        if cantidad_unidades <= 0:
            errores.append(f"Línea {i + 1}: la cantidad debe ser mayor a cero.")
            continue
        lineas.append((producto.id, cantidad_unidades))
    return lineas, errores


@bp.route("/")
def listar():
    salidas = SalidaCamion.query.order_by(SalidaCamion.fecha.desc(), SalidaCamion.id.desc()).all()
    filas = []
    for s in salidas:
        cerrada = s.retorno is not None
        venta = None
        if cerrada:
            detalle = venta_por_salida(s.id)
            venta = sum(d["valor"] for d in detalle) if detalle else 0
        filas.append({"salida": s, "cerrada": cerrada, "venta": venta})
    return render_template("camion/lista.html", filas=filas)


@bp.route("/<int:salida_id>")
def detalle(salida_id):
    salida = SalidaCamion.query.get_or_404(salida_id)
    venta = venta_por_salida(salida_id)
    return render_template("camion/detalle.html", salida=salida, venta=venta)


@bp.route("/salida/nueva", methods=["GET", "POST"])
def salida_nueva():
    productos = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()
    producto_por_id = {p.id: p for p in productos}

    if request.method == "POST":
        fecha = _parsear_fecha("fecha")
        lineas, errores = _parsear_lineas(producto_por_id)
        if not lineas:
            errores.append("Debes agregar al menos un producto a la carga.")
        if errores:
            for e in errores:
                flash(e, "error")
            return render_template("camion/salida_formulario.html", productos=productos, form=request.form)

        salida = SalidaCamion(fecha=fecha, notas=request.form.get("notas") or None)
        salida.detalles = [
            SalidaCamionDetalle(producto_id=pid, cantidad_unidades=qty) for pid, qty in lineas
        ]
        db.session.add(salida)
        db.session.commit()
        flash("Salida de camión registrada.", "success")
        return redirect(url_for("camion.listar"))

    return render_template("camion/salida_formulario.html", productos=productos, form=None)


@bp.route("/retorno/nueva")
def retorno_elegir():
    abiertas = rutas_en_transito()
    return render_template("camion/retorno_elegir.html", abiertas=abiertas)


@bp.route("/retorno/nueva/<int:salida_id>", methods=["GET", "POST"])
def retorno_nueva(salida_id):
    salida = SalidaCamion.query.get_or_404(salida_id)
    if salida.retorno is not None:
        flash("Esa salida ya tiene un retorno registrado.", "error")
        return redirect(url_for("camion.detalle", salida_id=salida_id))

    if request.method == "POST":
        fecha = _parsear_fecha("fecha")
        detalles = []
        for det in salida.detalles:
            campo = f"regreso_{det.producto_id}"
            try:
                cantidad = float(request.form.get(campo) or 0)
            except ValueError:
                cantidad = 0
            cantidad_unidades = round(cantidad)
            if cantidad_unidades > det.cantidad_unidades:
                flash(
                    f"{det.producto.nombre}: no puede regresar más de lo que salió ({det.cantidad_unidades}).",
                    "error",
                )
                return render_template("camion/retorno_formulario.html", salida=salida, form=request.form)
            detalles.append(RetornoCamionDetalle(producto_id=det.producto_id, cantidad_unidades=cantidad_unidades))

        retorno = RetornoCamion(salida_id=salida.id, fecha=fecha, notas=request.form.get("notas") or None)
        retorno.detalles = detalles
        db.session.add(retorno)
        db.session.commit()
        flash("Retorno de camión registrado. Inventario actualizado.", "success")
        return redirect(url_for("camion.detalle", salida_id=salida.id))

    return render_template("camion/retorno_formulario.html", salida=salida, form=None)
