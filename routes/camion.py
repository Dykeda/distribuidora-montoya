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
        venta_implicita = efectivo_por_salida(salida_id) or 0
        gasto_en_ruta = salida.retorno.gasto_en_ruta or 0
        creditos_pagados = salida.retorno.creditos_pagados or 0
        nuevos_creditos = salida.retorno.nuevos_creditos or 0
        efectivo_esperado = venta_implicita - gasto_en_ruta + nuevos_creditos + creditos_pagados
        efectivo_real = salida.retorno.efectivo_contado + salida.retorno.monedas_contado
        venta_total = venta_implicita + creditos_pagados
        cuadre = {
            "venta_implicita": venta_implicita,
            "gasto_en_ruta": gasto_en_ruta,
            "creditos_pagados": creditos_pagados,
            "nuevos_creditos": nuevos_creditos,
            "esperado": efectivo_esperado,
            "efectivo_contado": salida.retorno.efectivo_contado,
            "monedas_contado": salida.retorno.monedas_contado,
            "real": efectivo_real,
            "diferencia": efectivo_esperado - venta_total,
            "venta_total": venta_total,
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
    """Crea el retorno de una ruta, o lo actualiza si ya existe -- así siempre se puede
    corregir un retorno ya registrado (cantidades, cuadre de caja) sin tener que borrar
    nada a mano."""
    salida = SalidaCamion.query.get_or_404(salida_id)
    retorno_existente = salida.retorno

    cargado = cargado_por_producto(salida)  # incluye salida inicial + recargas del día
    regresado_previo = {d.producto_id: d.cantidad_unidades for d in retorno_existente.detalles} if retorno_existente else {}
    filas = []
    for pid, cant in cargado.items():
        producto = db.session.get(Producto, pid)
        cajas_cargadas, unidades_sueltas_cargadas = cajas_y_unidades(producto, cant)
        cajas_prev, unidades_prev = cajas_y_unidades(producto, regresado_previo.get(pid, 0))
        filas.append({
            "producto": producto,
            "cantidad_cargada": cant,
            "cajas_cargadas": cajas_cargadas,
            "unidades_sueltas_cargadas": unidades_sueltas_cargadas,
            "cajas_previas": cajas_prev,
            "unidades_previas": unidades_prev,
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
                return render_template("camion/retorno_formulario.html", salida=salida, filas=filas, form=request.form, retorno_existente=retorno_existente)
            detalles.append(RetornoCamionDetalle(producto_id=fila["producto"].id, cantidad_unidades=cantidad_unidades))

        efectivo_contado = None
        monedas_contado = None
        if request.form.get("efectivo_contado") or request.form.get("monedas_contado"):
            try:
                efectivo_contado = int(request.form.get("efectivo_contado") or 0)
                monedas_contado = int(request.form.get("monedas_contado") or 0)
            except ValueError:
                efectivo_contado = monedas_contado = None

        try:
            gasto_en_ruta = int(request.form.get("gasto_en_ruta") or 0)
        except ValueError:
            gasto_en_ruta = 0
        try:
            creditos_pagados = int(request.form.get("creditos_pagados") or 0)
        except ValueError:
            creditos_pagados = 0
        try:
            nuevos_creditos = int(request.form.get("nuevos_creditos") or 0)
        except ValueError:
            nuevos_creditos = 0

        if retorno_existente is not None:
            retorno_existente.fecha = fecha
            retorno_existente.notas = request.form.get("notas") or None
            retorno_existente.efectivo_contado = efectivo_contado
            retorno_existente.monedas_contado = monedas_contado
            retorno_existente.gasto_en_ruta = gasto_en_ruta
            retorno_existente.creditos_pagados = creditos_pagados
            retorno_existente.nuevos_creditos = nuevos_creditos
            retorno_existente.detalles = detalles
            db.session.commit()
            flash("Retorno de camión actualizado. Inventario recalculado.", "success")
        else:
            retorno = RetornoCamion(
                salida_id=salida.id, fecha=fecha, notas=request.form.get("notas") or None,
                efectivo_contado=efectivo_contado, monedas_contado=monedas_contado,
                gasto_en_ruta=gasto_en_ruta, creditos_pagados=creditos_pagados, nuevos_creditos=nuevos_creditos,
            )
            retorno.detalles = detalles
            db.session.add(retorno)
            db.session.commit()
            flash("Retorno de camión registrado. Inventario actualizado.", "success")
        return redirect(url_for("camion.detalle", salida_id=salida.id))

    return render_template("camion/retorno_formulario.html", salida=salida, filas=filas, form=None, retorno_existente=retorno_existente)


@bp.route("/recarga/nueva")
def recarga_elegir():
    abiertas = rutas_en_transito()
    return render_template("camion/recarga_elegir.html", abiertas=abiertas)


@bp.route("/recarga/nueva/<int:salida_id>", methods=["GET", "POST"])
def recarga_nueva(salida_id):
    salida = SalidaCamion.query.get_or_404(salida_id)
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


@bp.route("/recarga/<int:recarga_id>/eliminar", methods=["POST"])
def recarga_eliminar(recarga_id):
    recarga = RecargaCamion.query.get_or_404(recarga_id)
    salida_id = recarga.salida_id
    db.session.delete(recarga)
    db.session.commit()
    flash("Recarga eliminada. El inventario se recalcula solo.", "success")
    return redirect(url_for("camion.detalle", salida_id=salida_id))


@bp.route("/<int:salida_id>/carga/nueva", methods=["GET", "POST"])
def carga_nueva(salida_id):
    salida = SalidaCamion.query.get_or_404(salida_id)
    productos = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()

    if request.method == "POST":
        producto = db.session.get(Producto, int(request.form.get("producto_id") or 0))
        try:
            cajas = float(request.form.get("cajas") or 0)
            unidades = float(request.form.get("unidades") or 0)
        except ValueError:
            producto = None

        if producto is None:
            flash("Selecciona un producto válido.", "error")
            return render_template("camion/carga_nueva_formulario.html", salida=salida, productos=productos, form=request.form)

        cantidad_unidades = round(cajas * producto.unidades_por_caja + unidades)
        if cantidad_unidades <= 0:
            flash("La cantidad debe ser mayor a cero.", "error")
            return render_template("camion/carga_nueva_formulario.html", salida=salida, productos=productos, form=request.form)

        salida.detalles.append(SalidaCamionDetalle(producto_id=producto.id, cantidad_unidades=cantidad_unidades))
        db.session.commit()
        flash("Producto agregado a la carga.", "success")
        return redirect(url_for("camion.detalle", salida_id=salida.id))

    return render_template("camion/carga_nueva_formulario.html", salida=salida, productos=productos, form=None)


@bp.route("/<int:salida_id>/carga/<int:detalle_id>/editar", methods=["GET", "POST"])
def carga_editar(salida_id, detalle_id):
    salida = SalidaCamion.query.get_or_404(salida_id)
    detalle = SalidaCamionDetalle.query.filter_by(id=detalle_id, salida_id=salida_id).first_or_404()
    producto = detalle.producto

    if request.method == "POST":
        try:
            cajas = float(request.form.get("cajas") or 0)
            unidades = float(request.form.get("unidades") or 0)
        except ValueError:
            cajas = unidades = 0

        cantidad_unidades = round(cajas * producto.unidades_por_caja + unidades)
        if cantidad_unidades <= 0:
            flash("La cantidad debe ser mayor a cero.", "error")
        elif salida.retorno and _regresado_de(salida.retorno, producto.id) > (cargado_por_producto(salida)[producto.id] - detalle.cantidad_unidades + cantidad_unidades):
            flash(
                f"{producto.nombre}: ya hay un retorno registrado con más cantidad regresada de la que quedaría cargada. Corrige primero el retorno.",
                "error",
            )
        else:
            detalle.cantidad_unidades = cantidad_unidades
            db.session.commit()
            flash("Carga actualizada.", "success")
            return redirect(url_for("camion.detalle", salida_id=salida_id))

    cajas_actual, unidades_actual = cajas_y_unidades(producto, detalle.cantidad_unidades)
    return render_template(
        "camion/carga_editar_formulario.html", salida=salida, detalle=detalle, producto=producto,
        cajas_actual=cajas_actual, unidades_actual=unidades_actual,
    )


@bp.route("/<int:salida_id>/carga/<int:detalle_id>/eliminar", methods=["POST"])
def carga_eliminar(salida_id, detalle_id):
    salida = SalidaCamion.query.get_or_404(salida_id)
    detalle = SalidaCamionDetalle.query.filter_by(id=detalle_id, salida_id=salida_id).first_or_404()

    if salida.retorno and _regresado_de(salida.retorno, detalle.producto_id) > 0:
        flash(
            f"{detalle.producto.nombre}: ya hay un retorno registrado con cantidad regresada de este producto. Corrige primero el retorno.",
            "error",
        )
        return redirect(url_for("camion.detalle", salida_id=salida_id))

    db.session.delete(detalle)
    db.session.commit()
    flash("Producto quitado de la carga.", "success")
    return redirect(url_for("camion.detalle", salida_id=salida_id))


def _regresado_de(retorno, producto_id):
    detalle = next((d for d in retorno.detalles if d.producto_id == producto_id), None)
    return detalle.cantidad_unidades if detalle else 0
