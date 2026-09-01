import io
from datetime import date

import pytest

from models import Producto, ProductoPrecio, CodigoPostobon
from services.factura_postobon_pdf import (
    parsear_totales_footer,
    parsear_encabezado_desde_texto,
    parsear_lineas_desde_palabras,
    _descripciones_por_codigo,
)


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"password": app.config["APP_PASSWORD"]})
    return c


def crear_producto(db, nombre="Pet 400 Gopack 400", precio=1750):
    p = Producto(nombre=nombre, unidades_por_caja=15, maneja_cajas=True, maneja_unidades=True)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, precio_venta_caja=precio * 15, vigente_desde=date(2026, 1, 1)))
    db.session.commit()
    return p


# --- parsear_totales_footer ------------------------------------------------------

def test_parsear_totales_footer_formato_mixto_real():
    # SUB TOTAL/DESCUENTO en formato colombiano (punto miles, coma decimal);
    # IVA/VR. TOTAL FACTURA con coma de miles y punto decimal -- tal como viene el PDF.
    texto = (
        "SUB TOTAL 2.078.704,32\n"
        "DESCUENTO 249.338,20\n"
        "IVA 19.00% 219,949.44\n"
        "IBUA $0 0.00\n"
        "VR. TOTAL FACTURA COP 2,049,315.56\n"
    )
    totales = parsear_totales_footer(texto)
    assert totales["subtotal"] == 2078704.32
    assert totales["descuento"] == 249338.20
    assert totales["iva"] == 219949.44
    assert totales["total"] == 2049315.56


def test_parsear_totales_footer_sin_descuento_asume_cero():
    texto = "SUB TOTAL 1.198.740,90\nDESCUENTO\nIVA 19.00% 199,859.27\nVR. TOTAL FACTURA COP 1,398,600.17\n"
    totales = parsear_totales_footer(texto)
    assert totales["descuento"] == 0.0
    assert totales["subtotal"] == 1198740.90


# --- parsear_encabezado_desde_texto -----------------------------------------------

def test_parsear_encabezado_numero_factura_y_fecha():
    texto = "CUFE: abc123 FACTURA ELECTR�NICA DE VENTA No. AS07199731\n"
    tablas = [[[None, None, "FECHA EXPEDICI�N\n29/08/2026", "ORDEN DE COMPRA\n004", None]]]
    encabezado = parsear_encabezado_desde_texto(texto, tablas)
    assert encabezado["numero_factura"] == "AS07199731"
    assert encabezado["fecha"] == date(2026, 8, 29)


def test_parsear_encabezado_sin_tablas_no_falla():
    encabezado = parsear_encabezado_desde_texto("FACTURA ELECTR�NICA DE VENTA No. AS07198792\n", tablas=None)
    assert encabezado["numero_factura"] == "AS07198792"
    assert encabezado["fecha"] is None


# --- _descripciones_por_codigo ----------------------------------------------------

def test_descripciones_por_codigo_corta_antes_de_pza():
    texto = "31844 1.- |AGUA CRISTAL PLANA PET PZA 259.00 583.33 151,082.47 151,082.47\n"
    descripciones = _descripciones_por_codigo(texto)
    assert descripciones["31844"] == "AGUA CRISTAL PLANA PET"


def test_descripciones_por_codigo_ignora_lineas_de_continuacion():
    texto = "23663 2.- |LULO HIT 250 ML VIDRIO R X 30 PZA 360.00 1,050.42 302,520.95\n300ML X24 S.PRECI\n"
    descripciones = _descripciones_por_codigo(texto)
    assert descripciones["23663"] == "LULO HIT 250 ML VIDRIO R X 30"
    assert len(descripciones) == 1


# --- parsear_lineas_desde_palabras (posición x/y) ---------------------------------

def _palabra(texto, top, x0, x1):
    return {"text": texto, "top": top, "x0": x0, "x1": x1}


def _encabezado_columnas():
    """Palabras del encabezado de la tabla, con las mismas posiciones relativas que
    aparecen en las facturas reales."""
    return [
        _palabra("REFERENCIA", 191.0, 26.0, 65.0),
        _palabra("CANTIDAD", 191.0, 222.8, 254.2),
        _palabra("UNITARIO", 191.9, 274.0, 303.0),   # precio base
        _palabra("UNITARIO", 191.9, 328.5, 357.5),   # precio neto
        _palabra("DESCUENTO", 191.9, 375.5, 413.2),
        _palabra("%IVA", 191.0, 425.3, 440.7),
        _palabra("VLR.IVA", 191.0, 458.2, 481.8),
        _palabra("OTROS", 191.9, 500.8, 522.2),
        _palabra("VLR.TOTAL", 191.0, 543.7, 577.3),
    ]


def test_parsear_linea_completa_con_descuento_iva_y_otros():
    # Caso con las 4 columnas intermedias presentes (como "NARANJA POSTOBON 400 ML").
    palabras = _encabezado_columnas() + [
        _palabra("23929", 213.2, 36.5, 54.5),
        _palabra("75.00", 213.2, 229.9, 246.1),
        _palabra("1,750.70", 212.7, 290.7, 316.0),
        _palabra("111,607.12", 212.7, 334.5, 367.0),
        _palabra("19,695.38", 212.7, 387.1, 416.0),
        _palabra("19.00", 213.2, 424.4, 440.6),
        _palabra("21,205.35", 212.7, 462.1, 491.0),
        _palabra("0.00", 212.7, 516.4, 529.0),
        _palabra("132,812.47", 212.7, 556.5, 589.0),
    ]
    lineas = parsear_lineas_desde_palabras(palabras)
    assert len(lineas) == 1
    l = lineas[0]
    assert l["codigo"] == "23929"
    assert l["cantidad"] == 75
    assert l["costo_linea"] == 111607
    assert l["tasa_descuento_aplicada"] == 15.0
    assert l["porcentaje_iva"] == 19.0


def test_parsear_linea_con_iva_pero_sin_columna_otros():
    # Este es el caso real que rompía el parseo por conteo de columnas: descuento + IVA
    # presentes, pero la columna "VLR. IC Y/O OTROS" viene vacía (sin "0.00" impreso).
    palabras = _encabezado_columnas() + [
        _palabra("23584", 229.2, 36.5, 54.5),
        _palabra("24.00", 229.2, 229.9, 246.1),
        _palabra("840.34", 228.7, 296.1, 316.0),
        _palabra("18,520.42", 228.7, 338.1, 367.0),
        _palabra("1,647.74", 228.7, 390.7, 416.0),
        _palabra("19.00", 229.2, 424.4, 440.6),
        _palabra("3,518.88", 228.7, 465.7, 491.0),
        # sin "OTROS" -- la fila salta directo a VLR.TOTAL
        _palabra("22,039.30", 228.7, 560.1, 589.0),
    ]
    lineas = parsear_lineas_desde_palabras(palabras)
    assert len(lineas) == 1
    l = lineas[0]
    assert l["costo_linea"] == 18520
    assert l["porcentaje_iva"] == 19.0  # antes se leía 1647.74 (el descuento) por error
    assert l["tasa_descuento_aplicada"] == round(1647.74 / (24 * 840.34) * 100, 2)


def test_parsear_linea_sin_descuento_ni_iva():
    palabras = _encabezado_columnas() + [
        _palabra("23197", 203.2, 36.5, 54.5),
        _palabra("109.00", 203.2, 229.9, 246.1),
        _palabra("2,287.50", 202.7, 290.7, 316.0),
        _palabra("249,337.50", 202.7, 334.5, 367.0),
        _palabra("249,337.50", 202.7, 556.5, 589.0),
    ]
    lineas = parsear_lineas_desde_palabras(palabras)
    assert len(lineas) == 1
    assert lineas[0]["costo_linea"] == 249338
    assert lineas[0]["tasa_descuento_aplicada"] == 0.0
    assert lineas[0]["porcentaje_iva"] == 0.0


def test_parsear_lineas_sin_encabezado_devuelve_vacio():
    assert parsear_lineas_desde_palabras([_palabra("23929", 213.2, 36.5, 54.5)]) == []


# --- buscar_producto_por_codigo integrado dentro de parsear_pdf_postobon ---------

def test_buscar_producto_por_codigo_ya_asignado(db):
    gopack = crear_producto(db)
    db.session.add(CodigoPostobon(codigo="23929", producto_id=gopack.id, notas="Naranja"))
    db.session.commit()

    from services.codigos_postobon import buscar_producto_por_codigo
    assert buscar_producto_por_codigo("23929").id == gopack.id
    assert buscar_producto_por_codigo("99999") is None


# --- ruta /compras/cargar-pdf -----------------------------------------------------

def test_cargar_pdf_sin_archivo_muestra_error(client, db):
    r = client.post("/compras/cargar-pdf", data={}, content_type="multipart/form-data", follow_redirects=True)
    assert r.status_code == 200
    assert "Selecciona un archivo PDF" in r.get_data(as_text=True)


def test_cargar_pdf_archivo_invalido_muestra_error(client, db):
    archivo = (io.BytesIO(b"esto no es un PDF real"), "factura.pdf")
    r = client.post(
        "/compras/cargar-pdf", data={"archivo_pdf": archivo},
        content_type="multipart/form-data", follow_redirects=True,
    )
    assert r.status_code == 200
    assert "No se pudo leer ese PDF" in r.get_data(as_text=True)


def test_formulario_de_compra_apunta_a_guardar_incluso_despues_de_leer_pdf(client, db):
    # Bug real: cargar-pdf() re-renderiza compras/formulario.html desde la URL
    # /compras/cargar-pdf (no hace redirect) -- si el <form> de "Guardar compra" no
    # tiene action explícito, el navegador reenvía a esa misma URL de cargar-pdf en vez
    # de guardar la compra.
    archivo = (io.BytesIO(b"esto no es un PDF real"), "factura.pdf")
    r = client.post(
        "/compras/cargar-pdf", data={"archivo_pdf": archivo},
        content_type="multipart/form-data",
    )
    body = r.get_data(as_text=True)
    assert 'id="form-compra"' in body
    assert 'action="/compras/nueva"' in body
