from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash

from extensions import db
from models import Producto, ProductoPrecio
from services.inventario import listar_stock_todos

bp = Blueprint("productos", __name__, url_prefix="/productos")


@bp.route("/")
def listar():
    q = request.args.get("q", "").strip()
    query = Producto.query.filter_by(activo=True)
    if q:
        query = query.filter(Producto.nombre.ilike(f"%{q}%"))
    productos = query.order_by(Producto.nombre).all()
    return render_template("productos/lista.html", productos=productos, q=q)


@bp.route("/inventario")
def inventario():
    q = request.args.get("q", "").strip()
    filas = listar_stock_todos()
    if q:
        filas = [f for f in filas if q.lower() in f["producto"].nombre.lower()]
    return render_template("productos/inventario.html", filas=filas, q=q)


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        try:
            nombre = request.form["nombre"].strip()
            precio = int(request.form["precio_venta_unidad"])
            unidades_por_caja = int(request.form.get("unidades_por_caja") or 1)
            if not nombre:
                raise ValueError("El nombre es obligatorio.")
        except (KeyError, ValueError) as e:
            flash(f"Datos inválidos: {e}", "error")
            return render_template("productos/formulario.html", producto=None, form=request.form)

        try:
            tasa_descuento_referencia = float(request.form.get("tasa_descuento_referencia") or 0)
        except ValueError:
            tasa_descuento_referencia = 0.0

        p = Producto(
            nombre=nombre,
            categoria=request.form.get("categoria") or None,
            unidades_por_caja=unidades_por_caja,
            maneja_cajas=bool(request.form.get("maneja_cajas")),
            maneja_unidades=bool(request.form.get("maneja_unidades")),
            tasa_descuento_referencia=tasa_descuento_referencia,
        )
        db.session.add(p)
        db.session.flush()
        db.session.add(
            ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, vigente_desde=date.today())
        )
        db.session.commit()
        flash(f'Producto "{nombre}" creado.', "success")
        return redirect(url_for("productos.listar"))

    return render_template("productos/formulario.html", producto=None, form=None)


@bp.route("/<int:producto_id>/editar", methods=["GET", "POST"])
def editar(producto_id):
    p = Producto.query.get_or_404(producto_id)
    if request.method == "POST":
        try:
            nombre = request.form["nombre"].strip()
            nuevo_precio = int(request.form["precio_venta_unidad"])
            unidades_por_caja = int(request.form.get("unidades_por_caja") or 1)
            if not nombre:
                raise ValueError("El nombre es obligatorio.")
        except (KeyError, ValueError) as e:
            flash(f"Datos inválidos: {e}", "error")
            return render_template("productos/formulario.html", producto=p, form=request.form)

        try:
            tasa_descuento_referencia = float(request.form.get("tasa_descuento_referencia") or 0)
        except ValueError:
            tasa_descuento_referencia = 0.0

        p.nombre = nombre
        p.categoria = request.form.get("categoria") or None
        p.unidades_por_caja = unidades_por_caja
        p.maneja_cajas = bool(request.form.get("maneja_cajas"))
        p.maneja_unidades = bool(request.form.get("maneja_unidades"))
        p.tasa_descuento_referencia = tasa_descuento_referencia

        precio_actual = p.precio_actual()
        if precio_actual != nuevo_precio:
            db.session.add(
                ProductoPrecio(producto_id=p.id, precio_venta_unidad=nuevo_precio, vigente_desde=date.today())
            )
        db.session.commit()
        flash(f'Producto "{nombre}" actualizado.', "success")
        return redirect(url_for("productos.listar"))

    return render_template("productos/formulario.html", producto=p, form=None)


@bp.route("/<int:producto_id>/desactivar", methods=["POST"])
def desactivar(producto_id):
    p = Producto.query.get_or_404(producto_id)
    p.activo = False
    db.session.commit()
    flash(f'Producto "{p.nombre}" desactivado.', "success")
    return redirect(url_for("productos.listar"))


@bp.route("/carga-masiva", methods=["GET", "POST"])
def carga_masiva():
    """Alta rápida de muchos productos a la vez, pegando una lista en formato:
    nombre; categoria; unidades_por_caja; precio_venta_unidad; tasa_descuento_referencia
    Una línea por producto. categoria y tasa_descuento_referencia son opcionales (pueden
    quedar vacías entre punto y coma)."""
    if request.method == "POST":
        texto = request.form.get("lineas", "")
        creados, errores = [], []
        for numero_linea, linea in enumerate(texto.splitlines(), start=1):
            linea = linea.strip()
            if not linea:
                continue
            partes = [x.strip() for x in linea.split(";")]
            if len(partes) < 4:
                errores.append(f"Línea {numero_linea}: faltan datos (se esperan al menos 4 campos separados por ;)")
                continue
            nombre, categoria, unidades_por_caja, precio = partes[0], partes[1], partes[2], partes[3]
            tasa_descuento_referencia = partes[4] if len(partes) > 4 else ""
            try:
                unidades_por_caja = int(unidades_por_caja or 1)
                precio = int(precio)
                tasa_descuento_referencia = float(tasa_descuento_referencia or 0)
                if not nombre:
                    raise ValueError("nombre vacío")
            except ValueError:
                errores.append(f"Línea {numero_linea}: unidades por caja, precio o descuento inválido")
                continue

            p = Producto(
                nombre=nombre,
                categoria=categoria or None,
                unidades_por_caja=unidades_por_caja,
                maneja_cajas=True,
                maneja_unidades=True,
                tasa_descuento_referencia=tasa_descuento_referencia,
            )
            db.session.add(p)
            db.session.flush()
            db.session.add(
                ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, vigente_desde=date.today())
            )
            creados.append(nombre)

        if creados:
            db.session.commit()
            flash(f"{len(creados)} producto(s) creado(s).", "success")
        if errores:
            flash("Algunas líneas no se pudieron procesar: " + " | ".join(errores), "error")
        if creados and not errores:
            return redirect(url_for("productos.listar"))

    return render_template("productos/carga_masiva.html")
