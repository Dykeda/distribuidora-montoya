from datetime import date

import pytest

from models import (
    Producto,
    ProductoPrecio,
    Compra,
    CompraDetalle,
    FacturaCartera,
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


def test_construir_workbook_incluye_todas_las_hojas(db):
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
    db.session.add(FacturaCartera(cliente="Tienda X", fecha=date(2026, 8, 2), monto=20000))
    db.session.commit()

    wb = construir_workbook()

    assert set(wb.sheetnames) == {
        "Productos", "Compras", "Camion Salidas", "Camion Retornos",
        "Cartera", "Gastos", "Descuentos Canjes", "Descuentos Ajustes", "Venta Bodega",
    }

    productos = wb["Productos"]
    assert productos.max_row == 2  # encabezado + 1 producto
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


def test_ruta_exportar_excel_descarga_archivo(client):
    r = client.get("/reportes/exportar-excel")
    assert r.status_code == 200
    assert r.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in r.headers.get("Content-Disposition", "")
