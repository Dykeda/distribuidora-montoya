import calendar
from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash

from extensions import db
from models import (
    Producto,
    SalidaCamion,
    SalidaCamionDetalle,
    RetornoCamion,
    RetornoCamionDetalle,
    RecargaCamion,
    RecargaCamionDetalle,
)
from services.ventas import venta_por_salida, rutas_en_transito, cargado_por_producto
from services.inventario import cajas_y_unidades
from services.caja import efectivo_por_salida
from services.fechas import MESES_ES

bp = Blueprint("camion", __name__, url_prefix="/camion")


def _parsear_fecha(nombre_campo):
    fecha_str = request.form.get(nombre_campo)
    try:
        return datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else date.today()
    except ValueError:
        return date.today()


def _parsear_lineas(producto_por_id):
    producto_ids = request.form.getlist("producto_id[]")
    cajas_lista = request.form.getlist("cajas[]")
    unidades_lista = request.form.getlist("unidades[]")

    lineas, errores = [], []
    for i, pid in enumerate(producto_ids):
        if not pid:
            continue
        try:
            producto = producto_por_id.get(int(pid))
            cajas = float(cajas_lista[i] or 0)
            unidades = float(unidades_lista[i] or 0)
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
        lineas.append((producto.id, cantidad_unidades))
    return lineas, errores


@bp.route("/")
def listar():
    hoy = date.today()
    anio = int(request.args.get("anio", hoy.year))
    mes = int(request.args.get("mes", hoy.month))

    ultimo_dia = calendar.monthrange(anio, mes)[1]
    fecha_inicio, fecha_fin = date(anio, mes, 1), date(anio, mes, ultimo_dia)

    salidas = (
        SalidaCamion.query.filter(SalidaCamion.fecha >= fecha_inicio, SalidaCamion.fecha <= fecha_fin)
        .order_by(SalidaCamion.fecha.desc(), SalidaCamion.id.desc())
        .all()
    )
    filas = []
    for s in salidas:
        cerrada = s.retorno is not None
        venta = None
        if cerrada:
            detalle = venta_por_salida(s.id)
            venta = sum(d["valor"] for d in detalle) if detalle else 0
        filas.append({"salida": s, "cerrada": cerrada, "venta": venta})
    return render_template("camion/lista.html", filas=filas, anio=anio, mes=mes, meses=MESES_ES)


def _con_cajas_y_unidades(items, cantidad_attr):
    filas = []
    for item in items:
        cajas, unidades_sueltas = cajas_y_unidades(item["producto"], item[cantidad_attr])
        filas.append({**item, "cajas": cajas, "unidades_sueltas": unidades_sueltas})
    return filas


@bp.route("/<int:salida_id>")
def detalle(salida_id):
    salida = SalidaCamion.query.get_or_404(salida_id)

    carga = []
    for d in salida.detalles:
        cajas, unidades_sueltas = cajas_y_unidades(d.producto, d.cantidad_unidades)
        carga.append({"detalle": d, "cajas": cajas, "unidades_sueltas": unidades_sueltas})

    recargas = []
    for r in salida.recargas:
        for d in r.detalles:
            cajas, unidades_sueltas = cajas_y_unidades(d.producto, d.cantidad_unidades)
            recargas.append({"recarga": r, "detalle": d, "cajas": cajas, "unidades_sueltas": unidades_sueltas})

    venta = venta_por_salida(salida_id)
    if venta is not None:
        venta = _con_cajas_y_unidades(venta, "cantidad_vendida")

    cuadre = None
    if salida.retorno and salida.retorno.efectivo_contado is not None and salida.retorno.monedas_contado is not None:
        efectivo_esperado = efectivo_por_salida(salida_id) or 0
        efectivo_real = salida.retorno.efectivo_contado + salida.retorno.monedas_contado
        cuadre = {
            "esperado": efectivo_esperado,
            "efectivo_contado": salida.retorno.efectivo_contado,
            "monedas_contado": salida.retorno.monedas_contado,
            "real": efectivo_real,
            "diferencia": efectivo_real - efectivo_esperado,
        }

    return render_template("camion/detalle.html", salida=salida, carga=carga, recargas=recargas, venta=venta, cuadre=cuadre)


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

    cargado = cargado_por_producto(salida)  # incluye salida inicial + recargas del día
    filas = []
    for pid, cant in cargado.items():
        producto = db.session.get(Producto, pid)
        cajas_cargadas, unidades_sueltas_cargadas = cajas_y_unidades(producto, cant)
        filas.append({
            "producto": producto,
            "cantidad_cargada": cant,
            "cajas_cargadas": cajas_cargadas,
            "unidades_sueltas_cargadas": unidades_sueltas_cargadas,
        })

    if request.method == "POST":
        fecha = _parsear_fecha("fecha")
        detalles = []
        for fila in filas:
            producto = fila["producto"]
            try:
                cajas = float(request.form.get(f"regreso_cajas_{producto.id}") or 0)
            except ValueError:
                cajas = 0
            try:
                unidades_sueltas = float(request.form.get(f"regreso_unidades_{producto.id}") or 0)
            except ValueError:
                unidades_sueltas = 0
            cantidad_unidades = round(cajas * producto.unidades_por_caja + unidades_sueltas)
            if cantidad_unidades > fila["cantidad_cargada"]:
                flash(
                    f"{fila['producto'].nombre}: no puede regresar más de lo que salió/se le recargó ({fila['cantidad_cargada']}).",
                    "error",
                )
                return render_template("camion/retorno_formulario.html", salida=salida, filas=filas, form=request.form)
            detalles.append(RetornoCamionDetalle(producto_id=fila["producto"].id, cantidad_unidades=cantidad_unidades))

        efectivo_contado = None
        monedas_contado = None
        if request.form.get("efectivo_contado") or request.form.get("monedas_contado"):
            try:
                efectivo_contado = int(request.form.get("efectivo_contado") or 0)
                monedas_contado = int(request.form.get("monedas_contado") or 0)
            except ValueError:
                efectivo_contado = monedas_contado = None

        retorno = RetornoCamion(
            salida_id=salida.id, fecha=fecha, notas=request.form.get("notas") or None,
            efectivo_contado=efectivo_contado, monedas_contado=monedas_contado,
        )
        retorno.detalles = detalles
        db.session.add(retorno)
        db.session.commit()
        flash("Retorno de camión registrado. Inventario actualizado.", "success")
        return redirect(url_for("camion.detalle", salida_id=salida.id))

    return render_template("camion/retorno_formulario.html", salida=salida, filas=filas, form=None)


@bp.route("/recarga/nueva")
def recarga_elegir():
    abiertas = rutas_en_transito()
    return render_template("camion/recarga_elegir.html", abiertas=abiertas)


@bp.route("/recarga/nueva/<int:salida_id>", methods=["GET", "POST"])
def recarga_nueva(salida_id):
    salida = SalidaCamion.query.get_or_404(salida_id)
    if salida.retorno is not None:
        flash("Esa salida ya está cerrada, no se le puede mandar más producto.", "error")
        return redirect(url_for("camion.detalle", salida_id=salida_id))

    productos = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()
    producto_por_id = {p.id: p for p in productos}

    if request.method == "POST":
        fecha = _parsear_fecha("fecha")
        lineas, errores = _parsear_lineas(producto_por_id)
        if not lineas:
            errores.append("Debes agregar al menos un producto a la recarga.")
        if errores:
            for e in errores:
                flash(e, "error")
            return render_template(
                "camion/recarga_formulario.html", salida=salida, productos=productos, form=request.form
            )

        recarga = RecargaCamion(salida_id=salida.id, fecha=fecha, notas=request.form.get("notas") or None)
        recarga.detalles = [
            RecargaCamionDetalle(producto_id=pid, cantidad_unidades=qty) for pid, qty in lineas
        ]
        db.session.add(recarga)
        db.session.commit()
        flash("Recarga registrada. Inventario actualizado.", "success")
        return redirect(url_for("camion.detalle", salida_id=salida.id))

    return render_template("camion/recarga_formulario.html", salida=salida, productos=productos, form=None)
