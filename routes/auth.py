from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, flash

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == current_app.config["APP_PASSWORD"]:
            session.permanent = True
            session["autenticado"] = True
            destino = request.args.get("next") or url_for("dashboard.index")
            return redirect(destino)
        flash("Contraseña incorrecta.", "error")

    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
