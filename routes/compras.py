from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash

from extensions import db
from models import Producto, Compra, CompraDetalle, Proveedor
from services.compras import bruto_linea as _bruto_linea
from services.inventario import cajas_y_unidades
from services.proveedores import listar_proveedores, proveedor_postobon

bp = Blueprint("compras", __name__, url_prefix="/compras")


def _es_postobon_compra(compra):
    """Nulo (compras viejas o sin proveedor elegido) se trata como Postobón -- mismo
    criterio que usa nueva() al elegir el parser y services/postobon.py al filtrar."""
    return compra.proveedor.es_postobon if compra.proveedor else True


@bp.route("/")
def listar():
    compras = Compra.query.order_by(Compra.fecha.desc(), Compra.id.desc()).all()
    filas = []
    for c in compras:
        costo_total = sum(d.costo_linea for d in c.detalles)
        iva_total = sum(d.valor_iva for d in c.detalles)
        filas.append({"compra": c, "total_a_pagar": costo_total + iva_total})
    total_general = sum(f["total_a_pagar"] for f in filas)
    return render_template("compras/lista.html", filas=filas, total_general=total_general)


@bp.route("/<int:compra_id>")
def detalle(compra_id):
    compra = Compra.query.get_or_404(compra_id)
    es_postobon = _es_postobon_compra(compra)
    filas = []
    for d in compra.detalles:
        cajas, unidades_sueltas = cajas_y_unidades(d.producto, d.cantidad_comprada_unidades)
        bruto = _bruto_linea(d)
        descuento = bruto - d.costo_linea
        # En modo simple (no-Postobón) la tasa que se guarda es sobre el valor bruto total
        # recibido (necesaria para reconstruir Subtotal/Descuento), pero lo que se muestra
        # es sobre lo que realmente se pagó -- "de las cajas que compré, cuánto más me
        # dieron de descuento" -- que es como lo piensa el usuario para estos proveedores.
        if es_postobon or d.costo_linea == 0:
            tasa_mostrar = d.tasa_descuento_aplicada
        else:
            tasa_mostrar = round(descuento / d.costo_linea * 100, 2)
        filas.append({
            "detalle": d, "cajas": cajas, "unidades_sueltas": unidades_sueltas,
            "bruto": bruto, "descuento": descuento, "tasa_mostrar": tasa_mostrar,
        })

    costo_total = sum(d.costo_linea for d in compra.detalles)
    iva_total = sum(d.valor_iva for d in compra.detalles)
    total_a_pagar = costo_total + iva_total
    subtotal_bruto = sum(f["bruto"] for f in filas)
    descuento_total = subtotal_bruto - costo_total

    return render_template(
        "compras/detalle.html", compra=compra, filas=filas,
        subtotal_bruto=subtotal_bruto, costo_total=costo_total, descuento_total=descuento_total,
        iva_total=iva_total, total_a_pagar=total_a_pagar,
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
    es_postobon = _es_postobon_compra(compra)

    if request.method == "POST" and es_postobon:
        producto = db.session.get(Producto, int(request.form.get("producto_id") or 0))
        try:
            cajas = float(request.form.get("cajas") or 0)
            unidades = float(request.form.get("unidades") or 0)
            costo = int(request.form.get("costo_linea") or 0)
            tasa = float(request.form.get("tasa_descuento") or 0)
            iva = float(request.form.get("porcentaje_iva") or 0)
            if request.form.get("costo_incluye_iva") and iva > 0:
                costo = round(costo / (1 + iva / 100.0))
        except ValueError:
            producto = None
        es_descuento = bool(request.form.get("es_descuento"))

        if producto is None:
            flash("Selecciona un producto válido.", "error")
            return render_template("compras/linea_nueva_formulario.html", compra=compra, productos=productos, es_postobon=True, form=request.form)

        cantidad_unidades = round(cajas * producto.unidades_por_caja + unidades)
        if cantidad_unidades <= 0:
            flash("La cantidad debe ser mayor a cero.", "error")
            return render_template("compras/linea_nueva_formulario.html", compra=compra, productos=productos, es_postobon=True, form=request.form)

        compra.detalles.append(
            CompraDetalle(
                producto_id=producto.id,
                cantidad_comprada_unidades=cantidad_unidades,
                costo_linea=costo,
                tasa_descuento_aplicada=tasa,
                es_descuento=es_descuento,
                porcentaje_iva=iva,
                notas=request.form.get("notas") or None,
            )
        )
        db.session.commit()
        flash("Producto agregado a la compra.", "success")
        return redirect(url_for("compras.detalle", compra_id=compra.id))

    if request.method == "POST":
        producto = db.session.get(Producto, int(request.form.get("producto_id_simple") or 0))
        if producto is None:
            flash("Selecciona un producto válido.", "error")
            return render_template("compras/linea_nueva_formulario.html", compra=compra, productos=productos, es_postobon=False, form=request.form)
        try:
            cajas_pagadas = float(request.form.get("cajas_pagadas") or 0)
            unidades_pagadas = float(request.form.get("unidades_pagadas") or 0)
            cajas_descuento = float(request.form.get("cajas_descuento") or 0)
            unidades_descuento = float(request.form.get("unidades_descuento") or 0)
            costo_pagado = int(request.form.get("costo_pagado") or 0)
        except ValueError:
            flash("Datos inválidos.", "error")
            return render_template("compras/linea_nueva_formulario.html", compra=compra, productos=productos, es_postobon=False, form=request.form)

        errores = []
        notas = request.form.get("notas") or None
        lineas_nuevas = _construir_lineas_simple(
            producto, cajas_pagadas, unidades_pagadas, cajas_descuento, unidades_descuento,
            costo_pagado, notas, errores, "Producto",
        )
        if errores:
            for e in errores:
                flash(e, "error")
            return render_template("compras/linea_nueva_formulario.html", compra=compra, productos=productos, es_postobon=False, form=request.form)

        compra.detalles.extend(lineas_nuevas)
        db.session.commit()
        flash("Producto agregado a la compra.", "success")
        return redirect(url_for("compras.detalle", compra_id=compra.id))

    return render_template("compras/linea_nueva_formulario.html", compra=compra, productos=productos, es_postobon=es_postobon, form=None)


@bp.route("/<int:compra_id>/linea/<int:detalle_id>/editar", methods=["GET", "POST"])
def linea_editar(compra_id, detalle_id):
    compra = Compra.query.get_or_404(compra_id)
    detalle = CompraDetalle.query.filter_by(id=detalle_id, compra_id=compra_id).first_or_404()
    producto = detalle.producto
    es_postobon = _es_postobon_compra(compra)

    if request.method == "POST" and es_postobon:
        try:
            cajas = float(request.form.get("cajas") or 0)
            unidades = float(request.form.get("unidades") or 0)
            costo = int(request.form.get("costo_linea") or 0)
            tasa = float(request.form.get("tasa_descuento") or 0)
            iva = float(request.form.get("porcentaje_iva") or 0)
        except ValueError:
            cajas = unidades = costo = tasa = iva = 0
        es_descuento = bool(request.form.get("es_descuento"))
        if request.form.get("costo_incluye_iva") and iva > 0:
            costo = round(costo / (1 + iva / 100.0))

        cantidad_unidades = round(cajas * producto.unidades_por_caja + unidades)
        if cantidad_unidades <= 0:
            flash("La cantidad debe ser mayor a cero.", "error")
        else:
            detalle.cantidad_comprada_unidades = cantidad_unidades
            detalle.costo_linea = costo
            detalle.tasa_descuento_aplicada = tasa
            detalle.es_descuento = es_descuento
            detalle.porcentaje_iva = iva
            detalle.notas = request.form.get("notas") or None
            db.session.commit()
            flash("Producto de la compra actualizado.", "success")
            return redirect(url_for("compras.detalle", compra_id=compra_id))

        return render_template(
            "compras/linea_formulario.html", compra=compra, detalle=detalle, producto=producto, es_postobon=True,
            cajas_actual=cajas, unidades_actual=unidades, es_descuento_actual=es_descuento, iva_actual=iva,
            notas_actual=request.form.get("notas") or "",
        )

    if request.method == "POST":
        try:
            cajas_pagadas = float(request.form.get("cajas_pagadas") or 0)
            unidades_pagadas = float(request.form.get("unidades_pagadas") or 0)
            cajas_descuento = float(request.form.get("cajas_descuento") or 0)
            unidades_descuento = float(request.form.get("unidades_descuento") or 0)
            costo_pagado = int(request.form.get("costo_pagado") or 0)
        except ValueError:
            cajas_pagadas = unidades_pagadas = cajas_descuento = unidades_descuento = costo_pagado = 0
        notas = request.form.get("notas") or None

        errores = []
        lineas_nuevas = _construir_lineas_simple(
            producto, cajas_pagadas, unidades_pagadas, cajas_descuento, unidades_descuento,
            costo_pagado, notas, errores, "Producto",
        )
        if errores:
            for e in errores:
                flash(e, "error")
            return render_template(
                "compras/linea_formulario.html", compra=compra, detalle=detalle, producto=producto, es_postobon=False,
                cajas_pagadas_actual=cajas_pagadas, unidades_pagadas_actual=unidades_pagadas,
                cajas_descuento_actual=cajas_descuento, unidades_descuento_actual=unidades_descuento,
                costo_pagado_actual=costo_pagado, notas_actual=notas or "",
            )

        # las hasta 2 lineas de este producto en la compra (pagada + descuento) se
        # reemplazan juntas -- el modo simple las trata como una sola entrada por producto
        for d in [d for d in compra.detalles if d.producto_id == detalle.producto_id]:
            compra.detalles.remove(d)
        compra.detalles.extend(lineas_nuevas)
        db.session.commit()
        flash("Producto de la compra actualizado.", "success")
        return redirect(url_for("compras.detalle", compra_id=compra_id))

    if es_postobon:
        cajas_actual, unidades_actual = cajas_y_unidades(producto, detalle.cantidad_comprada_unidades)
        return render_template(
            "compras/linea_formulario.html", compra=compra, detalle=detalle, producto=producto, es_postobon=True,
            cajas_actual=cajas_actual, unidades_actual=unidades_actual, es_descuento_actual=detalle.es_descuento,
            iva_actual=detalle.porcentaje_iva, notas_actual=detalle.notas or "",
        )

    lineas_producto = [d for d in compra.detalles if d.producto_id == detalle.producto_id]
    pagada = next((d for d in lineas_producto if not d.es_descuento), None)
    descuento = next((d for d in lineas_producto if d.es_descuento), None)
    cajas_pagadas_actual, unidades_pagadas_actual = cajas_y_unidades(producto, pagada.cantidad_comprada_unidades) if pagada else (0, 0)
    cajas_descuento_actual, unidades_descuento_actual = cajas_y_unidades(producto, descuento.cantidad_comprada_unidades) if descuento else (0, 0)
    notas_actual = (pagada.notas if pagada else None) or (descuento.notas if descuento else None) or ""
    return render_template(
        "compras/linea_formulario.html", compra=compra, detalle=detalle, producto=producto, es_postobon=False,
        cajas_pagadas_actual=cajas_pagadas_actual, unidades_pagadas_actual=unidades_pagadas_actual,
        cajas_descuento_actual=cajas_descuento_actual, unidades_descuento_actual=unidades_descuento_actual,
        costo_pagado_actual=pagada.costo_linea if pagada else 0, notas_actual=notas_actual,
    )


def _parsear_lineas_postobon(request, errores):
    producto_ids = request.form.getlist("producto_id[]")
    cajas_lista = request.form.getlist("cajas[]")
    unidades_lista = request.form.getlist("unidades[]")
    costos = request.form.getlist("costo_linea[]")
    tasas = request.form.getlist("tasa_descuento[]")
    es_descuentos = request.form.getlist("es_descuento[]")
    ivas = request.form.getlist("porcentaje_iva[]")
    costo_incluye_iva_lista = request.form.getlist("costo_incluye_iva[]")
    notas_lineas = request.form.getlist("notas_linea[]")

    lineas_validas = []
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
        if i < len(costo_incluye_iva_lista) and costo_incluye_iva_lista[i] == "1" and iva > 0:
            costo = round(costo / (1 + iva / 100.0))

        if producto is None:
            errores.append(f"Línea {i + 1}: producto no encontrado.")
            continue

        cantidad_unidades = round(cajas * producto.unidades_por_caja + unidades)
        if cantidad_unidades <= 0:
            errores.append(f"Línea {i + 1}: la cantidad debe ser mayor a cero.")
            continue

        notas_linea = notas_lineas[i].strip() if i < len(notas_lineas) and notas_lineas[i].strip() else None
        lineas_validas.append(
            CompraDetalle(
                producto_id=producto.id,
                cantidad_comprada_unidades=cantidad_unidades,
                costo_linea=costo,
                tasa_descuento_aplicada=tasa,
                es_descuento=es_descuento,
                porcentaje_iva=iva,
                notas=notas_linea,
            )
        )
    return lineas_validas


def _construir_lineas_simple(producto, cajas_pagadas, unidades_pagadas, cajas_descuento,
                              unidades_descuento, costo_pagado, notas, errores, etiqueta):
    """Modo simple (proveedores que no son Postobón, ej. Canasto): a partir de cajas/
    unidades pagadas + cajas/unidades de descuento (regalo) + lo que realmente se pagó --
    sin tasa % ni IVA -- arma hasta dos CompraDetalle: una "pagada" (con una
    tasa_descuento_aplicada calculada para que el Subtotal/Descuento reconstruido en el
    detalle de la compra cuadre) y una "de descuento" a costo $0 (el producto que llegó
    sin cobro), marcada es_descuento=True solo como registro de cantidad -- a propósito NO
    se contabiliza en la pantalla Descuentos/ganancia neta, que es específica del sistema
    de crédito de Postobón."""
    cantidad_pagada = round(cajas_pagadas * producto.unidades_por_caja + unidades_pagadas)
    cantidad_descuento = round(cajas_descuento * producto.unidades_por_caja + unidades_descuento)
    cantidad_total = cantidad_pagada + cantidad_descuento
    if cantidad_total <= 0:
        errores.append(f"{etiqueta}: la cantidad debe ser mayor a cero.")
        return []

    lineas = []
    if cantidad_pagada > 0:
        # tasa para que bruto = costo_pagado/(1-tasa/100) reconstruya el valor de
        # TODAS las unidades (pagadas + descuento) al mismo precio por unidad -- así el
        # Subtotal/Descuento que se ve en el detalle de la compra cuadra con "cuánto
        # valían todas" vs "cuánto se pagó realmente".
        tasa = round(cantidad_descuento / cantidad_total * 100, 2)
        lineas.append(CompraDetalle(
            producto_id=producto.id, cantidad_comprada_unidades=cantidad_pagada,
            costo_linea=costo_pagado, tasa_descuento_aplicada=tasa,
            es_descuento=False, porcentaje_iva=0.0, notas=notas,
        ))
    if cantidad_descuento > 0:
        lineas.append(CompraDetalle(
            producto_id=producto.id, cantidad_comprada_unidades=cantidad_descuento,
            costo_linea=0, tasa_descuento_aplicada=0.0,
            es_descuento=True, porcentaje_iva=0.0, notas=notas,
        ))
    return lineas


def _parsear_lineas_simple(request, errores):
    producto_ids = request.form.getlist("producto_id_simple[]")
    cajas_pagadas_lista = request.form.getlist("cajas_pagadas[]")
    unidades_pagadas_lista = request.form.getlist("unidades_pagadas[]")
    cajas_descuento_lista = request.form.getlist("cajas_descuento[]")
    unidades_descuento_lista = request.form.getlist("unidades_descuento[]")
    costos_pagados = request.form.getlist("costo_pagado[]")
    notas_lineas = request.form.getlist("notas_linea_simple[]")

    lineas_validas = []
    for i, pid in enumerate(producto_ids):
        if not pid:
            continue
        try:
            producto = db.session.get(Producto, int(pid))
            cajas_pagadas = float(cajas_pagadas_lista[i] or 0)
            unidades_pagadas = float(unidades_pagadas_lista[i] or 0)
            cajas_descuento = float(cajas_descuento_lista[i] or 0) if i < len(cajas_descuento_lista) else 0.0
            unidades_descuento = float(unidades_descuento_lista[i] or 0) if i < len(unidades_descuento_lista) else 0.0
            costo_pagado = int(costos_pagados[i] or 0)
        except (ValueError, IndexError, TypeError):
            errores.append(f"Línea {i + 1}: datos inválidos.")
            continue

        if producto is None:
            errores.append(f"Línea {i + 1}: producto no encontrado.")
            continue

        notas_linea = notas_lineas[i].strip() if i < len(notas_lineas) and notas_lineas[i].strip() else None
        lineas_validas.extend(_construir_lineas_simple(
            producto, cajas_pagadas, unidades_pagadas, cajas_descuento, unidades_descuento,
            costo_pagado, notas_linea, errores, f"Línea {i + 1}",
        ))
    return lineas_validas


@bp.route("/nueva", methods=["GET", "POST"])
def nueva():
    productos = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()
    proveedores = listar_proveedores()

    if request.method == "POST":
        fecha_str = request.form.get("fecha")
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else date.today()
        except ValueError:
            fecha = date.today()

        proveedor_id_str = request.form.get("proveedor_id")
        proveedor = db.session.get(Proveedor, int(proveedor_id_str)) if proveedor_id_str else None
        if proveedor is None:
            proveedor = proveedor_postobon()

        errores = []
        if proveedor.es_postobon:
            lineas_validas = _parsear_lineas_postobon(request, errores)
        else:
            lineas_validas = _parsear_lineas_simple(request, errores)

        if not lineas_validas:
            errores.append("Debes agregar al menos una línea de producto válida.")

        if errores:
            for e in errores:
                flash(e, "error")
            return render_template("compras/formulario.html", productos=productos, proveedores=proveedores, form=request.form)

        compra = Compra(
            fecha=fecha,
            numero_factura=request.form.get("numero_factura") or None,
            notas=request.form.get("notas") or None,
            proveedor_id=proveedor.id,
        )
        compra.detalles = lineas_validas
        db.session.add(compra)
        db.session.commit()
        flash("Compra registrada.", "success")
        return redirect(url_for("compras.listar"))

    return render_template("compras/formulario.html", productos=productos, proveedores=proveedores, form=None)
