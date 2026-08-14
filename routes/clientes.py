from flask import Blueprint, render_template, request, redirect, url_for, flash

from extensions import db
from models import Cliente
from services.clientes import resumen_clientes
from services.cartera import total_pendiente

bp = Blueprint("clientes", __name__, url_prefix="/clientes")


@bp.route("/")
def listar():
    return render_template("clientes/lista.html", filas=resumen_clientes())


@bp.route("/<int:cliente_id>")
def detalle(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    facturas = sorted(cliente.facturas, key=lambda f: f.fecha, reverse=True)
    return render_template(
        "clientes/detalle.html",
        cliente=cliente,
        facturas=facturas,
        total_pendiente=total_pendiente(cliente_id=cliente.id),
    )


@bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    destino = request.args.get("next") or url_for("clientes.listar")

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        destino = request.form.get("next") or destino

        errores = []
        if not nombre:
            errores.append("El nombre del cliente es obligatorio.")
        elif Cliente.query.filter_by(nombre=nombre).first():
            errores.append(f'Ya existe un cliente llamado "{nombre}".')

        if errores:
            for e in errores:
                flash(e, "error")
            return render_template("clientes/formulario.html", cliente=None, form=request.form, next=destino)

        cliente = Cliente(nombre=nombre, notas=request.form.get("notas") or None)
        db.session.add(cliente)
        db.session.commit()
        flash(f'Cliente "{nombre}" creado.', "success")
        separador = "&" if "?" in destino else "?"
        return redirect(f"{destino}{separador}cliente_id={cliente.id}")

    return render_template("clientes/formulario.html", cliente=None, form=None, next=destino)


@bp.route("/<int:cliente_id>/editar", methods=["GET", "POST"])
def editar(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()

        errores = []
        if not nombre:
            errores.append("El nombre del cliente es obligatorio.")
        elif Cliente.query.filter(Cliente.nombre == nombre, Cliente.id != cliente.id).first():
            errores.append(f'Ya existe un cliente llamado "{nombre}".')

        if errores:
            for e in errores:
                flash(e, "error")
            return render_template("clientes/formulario.html", cliente=cliente, form=request.form, next=None)

        cliente.nombre = nombre
        cliente.notas = request.form.get("notas") or None
        db.session.commit()
        flash(f'Cliente "{nombre}" actualizado.', "success")
        return redirect(url_for("clientes.detalle", cliente_id=cliente.id))

    return render_template("clientes/formulario.html", cliente=cliente, form=None, next=None)


@bp.route("/<int:cliente_id>/desactivar", methods=["POST"])
def desactivar(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    cliente.activo = False
    db.session.commit()
    flash(f'Cliente "{cliente.nombre}" desactivado.', "success")
    return redirect(url_for("clientes.listar"))
