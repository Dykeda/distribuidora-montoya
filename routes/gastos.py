from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash

from extensions import db
from models import CategoriaGasto, Gasto
from services.gastos import categorias_por_tipo, listar_gastos

bp = Blueprint("gastos", __name__, url_prefix="/gastos")


@bp.route("/")
def listar():
    tipo = request.args.get("tipo") or None
    if tipo not in (None, "negocio", "hogar"):
        tipo = None
    gastos = listar_gastos(tipo=tipo)
    total = sum(g.monto for g in gastos)
    return render_template("gastos/lista.html", gastos=gastos, total=total, tipo_activo=tipo)


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    categorias_negocio = categorias_por_tipo("negocio")
    categorias_hogar = categorias_por_tipo("hogar")

    if request.method == "POST":
        fecha_str = request.form.get("fecha")
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date() if fecha_str else date.today()
        except ValueError:
            fecha = date.today()

        errores = []
        categoria_id = request.form.get("categoria_id")
        categoria = db.session.get(CategoriaGasto, int(categoria_id)) if categoria_id else None
        if not categoria:
            errores.append("Debes elegir una categoría.")

        try:
            monto = int(request.form.get("monto") or 0)
            if monto <= 0:
                raise ValueError
        except ValueError:
            monto = 0
            errores.append("El monto debe ser un número mayor a cero.")

        if errores:
            for e in errores:
                flash(e, "error")
            return render_template(
                "gastos/formulario.html",
                categorias_negocio=categorias_negocio,
                categorias_hogar=categorias_hogar,
                form=request.form,
            )

        gasto = Gasto(categoria_id=categoria.id, fecha=fecha, monto=monto, notas=request.form.get("notas") or None)
        db.session.add(gasto)
        db.session.commit()
        flash(f'Salida registrada en "{categoria.nombre}". Caja actualizada.', "success")
        return redirect(url_for("gastos.listar"))

    return render_template(
        "gastos/formulario.html", categorias_negocio=categorias_negocio, categorias_hogar=categorias_hogar, form=None
    )


@bp.route("/categoria/nueva", methods=["GET", "POST"])
def categoria_nueva():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        tipo = request.form.get("tipo")

        errores = []
        if not nombre:
            errores.append("El nombre de la categoría es obligatorio.")
        if tipo not in ("negocio", "hogar"):
            errores.append("Debes elegir si es una categoría de negocio o de hogar.")

        if not errores:
            existe = CategoriaGasto.query.filter_by(nombre=nombre, tipo=tipo).first()
            if existe:
                errores.append(f'Ya existe una categoría "{nombre}" de ese tipo.')

        if errores:
            for e in errores:
                flash(e, "error")
            return render_template("gastos/categoria_formulario.html", form=request.form)

        db.session.add(CategoriaGasto(nombre=nombre, tipo=tipo))
        db.session.commit()
        flash(f'Categoría "{nombre}" creada.', "success")
        return redirect(url_for("gastos.nuevo"))

    return render_template("gastos/categoria_formulario.html", form=None)
