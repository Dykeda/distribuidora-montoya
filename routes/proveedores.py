from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

from extensions import db
from models import Proveedor
from services.proveedores import resumen_proveedores

bp = Blueprint("proveedores", __name__, url_prefix="/proveedores")


@bp.route("/")
def listar():
    return render_template("proveedores/lista.html", filas=resumen_proveedores())


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        es_postobon = bool(request.form.get("es_postobon"))

        errores = []
        if not nombre:
            errores.append("El nombre del proveedor es obligatorio.")
        elif Proveedor.query.filter_by(nombre=nombre).first():
            errores.append(f'Ya existe un proveedor llamado "{nombre}".')

        if errores:
            for e in errores:
                flash(e, "error")
            return render_template("proveedores/formulario.html", proveedor=None, form=request.form)

        proveedor = Proveedor(nombre=nombre, es_postobon=es_postobon, notas=request.form.get("notas") or None)
        db.session.add(proveedor)
        db.session.commit()
        flash(f'Proveedor "{nombre}" creado.', "success")
        return redirect(url_for("proveedores.listar"))

    return render_template("proveedores/formulario.html", proveedor=None, form=None)


@bp.route("/nuevo-ajax", methods=["POST"])
def nuevo_ajax():
    """Crea un proveedor sin navegar a otra página -- mismo patrón que
    clientes.nuevo_ajax, para usarlo desde el formulario de nueva compra sin perder las
    líneas de producto ya escritas. Siempre crea proveedores externos (es_postobon=False)
    -- Postobón ya existe sembrado, no hace falta crearlo desde aquí."""
    data = request.get_json(silent=True) or {}
    nombre = (data.get("nombre") or "").strip()

    if not nombre:
        return jsonify({"error": "El nombre del proveedor es obligatorio."}), 400
    if Proveedor.query.filter_by(nombre=nombre).first():
        return jsonify({"error": f'Ya existe un proveedor llamado "{nombre}".'}), 400

    proveedor = Proveedor(nombre=nombre, es_postobon=False)
    db.session.add(proveedor)
    db.session.commit()
    return jsonify({"id": proveedor.id, "nombre": proveedor.nombre}), 201


@bp.route("/<int:proveedor_id>/editar", methods=["GET", "POST"])
def editar(proveedor_id):
    proveedor = Proveedor.query.get_or_404(proveedor_id)

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        es_postobon = bool(request.form.get("es_postobon"))

        errores = []
        if not nombre:
            errores.append("El nombre del proveedor es obligatorio.")
        elif Proveedor.query.filter(Proveedor.nombre == nombre, Proveedor.id != proveedor.id).first():
            errores.append(f'Ya existe un proveedor llamado "{nombre}".')

        if errores:
            for e in errores:
                flash(e, "error")
            return render_template("proveedores/formulario.html", proveedor=proveedor, form=request.form)

        proveedor.nombre = nombre
        proveedor.es_postobon = es_postobon
        proveedor.notas = request.form.get("notas") or None
        db.session.commit()
        flash(f'Proveedor "{nombre}" actualizado.', "success")
        return redirect(url_for("proveedores.listar"))

    return render_template("proveedores/formulario.html", proveedor=proveedor, form=None)


@bp.route("/<int:proveedor_id>/desactivar", methods=["POST"])
def desactivar(proveedor_id):
    proveedor = Proveedor.query.get_or_404(proveedor_id)
    proveedor.activo = False
    db.session.commit()
    flash(f'Proveedor "{proveedor.nombre}" desactivado.', "success")
    return redirect(url_for("proveedores.listar"))
