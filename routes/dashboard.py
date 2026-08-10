import calendar
from datetime import date

from flask import Blueprint, render_template

from models import Producto
from services.inventario import listar_stock_todos
from services.reportes import resumen_periodo

bp = Blueprint("dashboard", __name__)

UMBRAL_STOCK_BAJO_CAJAS = 1


@bp.route("/")
def index():
    hoy = date.today()
    ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
    fecha_inicio, fecha_fin = date(hoy.year, hoy.month, 1), date(hoy.year, hoy.month, ultimo_dia)

    resumen = resumen_periodo(fecha_inicio, fecha_fin)

    stock = listar_stock_todos()
    stock_bajo = [
        f for f in stock
        if f["producto"].unidades_por_caja
        and f["stock_unidades"] < f["producto"].unidades_por_caja * UMBRAL_STOCK_BAJO_CAJAS
    ]

    return render_template(
        "dashboard.html",
        resumen=resumen,
        mes_actual=hoy.strftime("%B %Y"),
        stock_bajo=stock_bajo,
        hay_productos=Producto.query.first() is not None,
    )
