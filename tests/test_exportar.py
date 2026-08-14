import re
from datetime import date

import pytest

from models import (
    Producto,
    ProductoPrecio,
    Compra,
    CompraDetalle,
    SalidaCamion,
    SalidaCamionDetalle,
    RetornoCamion,
    RetornoCamionDetalle,
    FacturaCartera,
    Cliente,
)
from services.exportar import construir_workbook


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"password": app.config["APP_PASSWORD"]})
    return c


def crear_producto(db, nombre="Coca-Cola 1.5L", precio=3000):
    p = Producto(nombre=nombre, unidades_por_caja=6, maneja_cajas=True, maneja_unidades=True)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, precio_venta_caja=precio * 6, vigente_desde=date(2026, 1, 1)))
    db.session.commit()
    return p


def test_construir_workbook_incluye_todas_las_hojas_y_resumen_calculado(db):
    coca = crear_producto(db)

    compra = Compra(fecha=date(2026, 8, 1))
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=coca.id, cantidad_comprada_unidades=60,
            costo_linea=180000, tasa_descuento_aplicada=5.0,
        )
    )
    db.session.commit()

    salida = SalidaCamion(fecha=date(2026, 8, 2))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=30))
    db.session.commit()
    retorno = RetornoCamion(salida_id=salida.id, fecha=date(2026, 8, 2))
    db.session.add(retorno)
    db.session.flush()
    db.session.add(RetornoCamionDetalle(retorno_id=retorno.id, producto_id=coca.id, cantidad_unidades=6))
    db.session.commit()
    # vendido = 30 - 6 = 24 unidades * 3000 = 72000

    tienda_x = Cliente(nombre="Tienda X")
    db.session.add(tienda_x)
    db.session.flush()
    db.session.add(FacturaCartera(cliente_id=tienda_x.id, fecha=date(2026, 8, 2), monto=20000))
    db.session.commit()

    wb = construir_workbook()

    assert set(wb.sheetnames) == {
        "Resumen", "Rendimiento por producto", "Productos", "Compras",
        "Camion Salidas", "Camion Ventas", "Cartera", "Gastos",
        "Descuentos Canjes", "Descuentos Ajustes", "Venta Bodega",
    }

    resumen = {fila[0]: fila[1] for fila in wb["Resumen"].iter_rows(min_row=2, values_only=True)}
    assert resumen["Compra total (histórico)"] == 180000
    assert resumen["Venta total (histórico)"] == 72000
    assert resumen["Saldo de crédito acumulado"] == 9000
    assert resumen["Cartera pendiente por cobrar"] == 20000
    assert resumen["Saldo de caja acumulado"] == 72000  # la factura no está ligada a esta salida
    assert resumen["% de descuento promedio (ponderado, histórico)"] == 5.0
    assert resumen["Ganancia neta del negocio (histórico)"] == 9000  # credito generado, sin gastos

    rendimiento = wb["Rendimiento por producto"]
    assert rendimiento.cell(row=2, column=1).value == "Coca-Cola 1.5L"
    assert rendimiento.cell(row=2, column=3).value == 9000  # credito generado

    ventas_camion = wb["Camion Ventas"]
    assert ventas_camion.max_row == 2
    assert ventas_camion.cell(row=2, column=4).value == 24  # cantidad vendida
    assert ventas_camion.cell(row=2, column=6).value == 72000  # valor

    productos = wb["Productos"]
    assert productos.max_row == 2
    assert productos.cell(row=2, column=1).value == "Coca-Cola 1.5L"

    compras = wb["Compras"]
    assert compras.max_row == 2
    assert compras.cell(row=2, column=7).value == 9000  # credito generado

    cartera = wb["Cartera"]
    assert cartera.max_row == 2
    assert cartera.cell(row=2, column=1).value == "Tienda X"
    assert cartera.cell(row=2, column=3).value == "Deuda anterior"


def test_construir_workbook_sin_datos_no_falla(db):
    wb = construir_workbook()
    assert wb["Productos"].max_row == 1  # solo encabezado
    resumen = {fila[0]: fila[1] for fila in wb["Resumen"].iter_rows(min_row=2, values_only=True)}
    assert resumen["Compra total (histórico)"] == 0
    assert resumen["% de descuento promedio (ponderado, histórico)"] == 0.0
    assert resumen["Ganancia neta del negocio (histórico)"] == 0


def test_ruta_exportar_excel_descarga_archivo(client):
    r = client.get("/reportes/exportar-excel")
    assert r.status_code == 200
    assert r.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in r.headers.get("Content-Disposition", "")


def test_ruta_exportar_excel_nombre_incluye_fecha_y_hora(client):
    r = client.get("/reportes/exportar-excel")
    disposicion = r.headers.get("Content-Disposition", "")
    # ej. distribuidora_montoya_2026-08-14_1530.xlsx -- fecha y hora, no solo fecha
    assert re.search(r"distribuidora_montoya_\d{4}-\d{2}-\d{2}_\d{4}\.xlsx", disposicion)
