import calendar
from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash

from extensions import db
from models import CategoriaGasto, Gasto
from services.gastos import categorias_por_tipo, listar_gastos, totales_por_categoria
from services.fechas import MESES_ES

bp = Blueprint("gastos", __name__, url_prefix="/gastos")


@bp.route("/")
def listar():
    tipo = request.args.get("tipo") or None
    if tipo not in (None, "negocio", "hogar"):
        tipo = None

    categoria_id = request.args.get("categoria_id")
    categoria_id = int(categoria_id) if categoria_id else None

    periodo = request.args.get("periodo") or "todo"
    hoy = date.today()
    anio = int(request.args.get("anio", hoy.year))
    mes = int(request.args.get("mes", hoy.month))
    if periodo == "mes":
        ultimo_dia = calendar.monthrange(anio, mes)[1]
        fecha_inicio, fecha_fin = date(anio, mes, 1), date(anio, mes, ultimo_dia)
    else:
        fecha_inicio = fecha_fin = None

    categorias_filtro = categorias_por_tipo(tipo, solo_activas=False) if tipo else (
        categorias_por_tipo("negocio", solo_activas=False) + categorias_por_tipo("hogar", solo_activas=False)
    )

    gastos = listar_gastos(tipo=tipo, categoria_id=categoria_id, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
    total = sum(g.monto for g in gastos)
    totales_categoria = totales_por_categoria(tipo=tipo, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)

    return render_template(
        "gastos/lista.html", gastos=gastos, total=total, tipo_activo=tipo,
        categoria_id=categoria_id, categorias_filtro=categorias_filtro,
        periodo=periodo, anio=anio, mes=mes, meses=MESES_ES,
        totales_categoria=totales_categoria,
    )


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
