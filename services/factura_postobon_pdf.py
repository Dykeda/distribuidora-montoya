"""Lee una factura PDF real de Postobón (la "Representación Gráfica de Factura
Electrónica de Venta") y extrae fecha, número de factura, totales impresos y cada línea
de producto -- para precargar el formulario de "Registrar compra" en vez de transcribir
la factura a mano.

El parseo de las líneas de producto usa la POSICIÓN (x/y) de cada palabra en la página,
no el orden del texto ni la cantidad de números por línea -- la tabla real tiene columnas
que a veces vienen vacías en cualquier combinación (ej. "VALOR DESCUENTO" sin "%IVA", o
con "%IVA" pero sin el campo "OTROS"), así que solo la posición horizontal identifica de
forma confiable a qué columna pertenece cada número. Las funciones de más bajo nivel
reciben las palabras ya extraídas (no el PDF en sí) para poder probarlas con datos de
muestra, sin depender de un archivo real."""
import re
from datetime import datetime

import pdfplumber

from services.codigos_postobon import buscar_producto_por_codigo

_RE_NUMERO_FACTURA = re.compile(r"\bAS0\d{6,8}\b")
_RE_FECHA_EN_CELDA = re.compile(r"FECHA EXPEDICI.N\s*\n\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
_RE_SOLO_DIGITOS = re.compile(r"^\d{2,10}$")

_ETIQUETAS_COLUMNA = {
    "REFERENCIA": "codigo",
    "CANTIDAD": "cantidad",
    "UNITARIO": "_unitario",  # aparece dos veces: precio base (1a) y precio total/neto (2a)
    "DESCUENTO": "descuento",
    "%IVA": "iva_pct",
    "VLR.IVA": "vlr_iva",
    "OTROS": "otros",
    "VLR.TOTAL": "total",
}


def _a_float(texto):
    """'1,750.70' -> 1750.70 (la tabla de líneas usa coma para miles y punto para
    decimales)."""
    return float(texto.replace(",", ""))


def _a_float_colombiano(texto):
    """'2.078.704,32' -> 2078704.32 (el resumen SUB TOTAL/DESCUENTO/IVA al final de la
    factura, en cambio, usa el formato colombiano: punto de miles, coma decimal --
    inconsistente con la tabla de líneas, pero así viene en el PDF real)."""
    return float(texto.replace(".", "").replace(",", "."))


def _detectar_columnas(palabras):
    """Ubica el encabezado de la tabla de líneas y devuelve {clave: x_centro} para cada
    columna que necesitamos, usando la posición horizontal de cada etiqueta. Las dos
    apariciones de "UNITARIO" se separan en precio_base (más a la izquierda) y
    precio_neto (más a la derecha). Devuelve None si no encuentra el encabezado (PDF con
    un formato distinto al esperado)."""
    ref = next((w for w in palabras if w["text"] == "REFERENCIA"), None)
    if ref is None:
        return None
    fila_top = ref["top"]
    fila = [w for w in palabras if abs(w["top"] - fila_top) <= 2]

    columnas = {}
    unitarios = []
    for w in fila:
        clave = _ETIQUETAS_COLUMNA.get(w["text"])
        if clave is None:
            continue
        centro = (w["x0"] + w["x1"]) / 2
        if clave == "_unitario":
            unitarios.append(centro)
        else:
            columnas[clave] = centro

    if "codigo" not in columnas or "cantidad" not in columnas or len(unitarios) < 2:
        return None
    unitarios.sort()
    columnas["precio_base"] = unitarios[0]
    columnas["precio_neto"] = unitarios[1]
    return columnas


def _columna_mas_cercana(x_centro, columnas):
    mejor_clave, mejor_dist = None, None
    for clave, x in columnas.items():
        dist = abs(x_centro - x)
        if mejor_dist is None or dist < mejor_dist:
            mejor_clave, mejor_dist = clave, dist
    return mejor_clave


def parsear_lineas_desde_palabras(palabras):
    """Agrupa las palabras de la página en líneas de producto, usando "codigo" (columna
    REFERENCIA con puros dígitos) como ancla de cada fila, y ubica cada número de esa
    fila en su columna real por posición horizontal -- así una columna vacía (ej. sin
    descuento, o con IVA pero sin "otros") no corre el resto de los valores."""
    columnas = _detectar_columnas(palabras)
    if columnas is None:
        return []

    x_ref = columnas["codigo"]
    lineas = []
    for w in palabras:
        if not _RE_SOLO_DIGITOS.match(w["text"]):
            continue
        centro = (w["x0"] + w["x1"]) / 2
        if abs(centro - x_ref) > 15:
            continue  # no está en la columna REFERENCIA, es otro número

        fila_top = w["top"]
        codigo = w["text"]
        valores = {}
        for w2 in palabras:
            if abs(w2["top"] - fila_top) > 2:
                continue
            centro2 = (w2["x0"] + w2["x1"]) / 2
            if centro2 < columnas["cantidad"] - 15:
                continue  # columna REFERENCIA/DESCRIPCIÓN/UNIDAD -- no es un valor numérico de la fila
            clave = _columna_mas_cercana(centro2, {k: v for k, v in columnas.items() if k != "codigo"})
            texto = w2["text"]
            if not re.match(r"^[\d.,]+$", texto):
                continue
            valores.setdefault(clave, texto)

        if "cantidad" not in valores or "precio_neto" not in valores:
            continue

        cantidad = _a_float(valores["cantidad"])
        precio_base = _a_float(valores.get("precio_base", "0"))
        neto = _a_float(valores["precio_neto"])
        descuento_valor = _a_float(valores["descuento"]) if "descuento" in valores else 0.0
        iva_pct = _a_float(valores["iva_pct"]) if "iva_pct" in valores else 0.0

        bruto = cantidad * precio_base
        tasa = round(descuento_valor / bruto * 100, 2) if bruto > 0 else 0.0

        lineas.append({
            "codigo": codigo,
            "cantidad": round(cantidad),
            "costo_linea": round(neto),
            "tasa_descuento_aplicada": tasa,
            "porcentaje_iva": iva_pct,
        })
    return lineas


def _descripciones_por_codigo(texto):
    """Solo para mostrarle al usuario qué producto es cada código sin resolver todavía
    -- no se usa para ningún cálculo. Toma la primera línea de texto que empieza con
    cada código (la descripción puede venir cortada si se parte en dos líneas)."""
    descripciones = {}
    for renglon in texto.splitlines():
        m = re.match(r"^(\d{2,10})\s+\d+\.-\s*\|(.+?)(?:\s+PZA\b.*)?$", renglon.strip())
        if m:
            descripciones.setdefault(m.group(1), m.group(2).strip())
    return descripciones


def parsear_encabezado_desde_texto(texto, tablas=None):
    """numero_factura sale del texto plano (aparece en una sola línea, junto al CUFE).
    fecha (FECHA EXPEDICIÓN) en cambio hay que sacarla de una celda de tabla -- en el
    texto plano la etiqueta y el valor quedan en líneas distintas, entreverados con
    otras columnas de la misma fila, porque son celdas de una tabla de encabezado."""
    numero_factura = None
    m = _RE_NUMERO_FACTURA.search(texto)
    if m:
        numero_factura = m.group(0)

    fecha = None
    for tabla in (tablas or []):
        for fila in tabla:
            for celda in fila:
                if not celda or "EXPEDICI" not in celda:
                    continue
                m = _RE_FECHA_EN_CELDA.search(celda)
                if m:
                    try:
                        fecha = datetime.strptime(m.group(1), "%d/%m/%Y").date()
                    except ValueError:
                        fecha = None
                    break
            if fecha:
                break
        if fecha:
            break

    return {"numero_factura": numero_factura, "fecha": fecha}


def parsear_totales_footer(texto):
    """Los totales que la propia factura imprime al final (Subtotal/Descuento/IVA/Total)
    -- para poder comparar contra lo que se reconstruye a partir de las líneas y avisar
    si algo no cuadra, igual que se ha venido verificando a mano. Ojo: en el PDF real,
    SUB TOTAL/DESCUENTO vienen en formato colombiano (punto de miles, coma decimal) pero
    IVA/VR. TOTAL FACTURA vienen con coma de miles y punto decimal -- inconsistente entre
    sí, pero así lo genera la plantilla de Postobón."""

    def _buscar(patron, convertir, default=None):
        m = re.search(patron, texto)
        return convertir(m.group(1)) if m else default

    return {
        "subtotal": _buscar(r"SUB TOTAL\s+([\d.,]+)", _a_float_colombiano),
        "descuento": _buscar(r"DESCUENTO\s+([\d.,]+)", _a_float_colombiano, default=0.0),
        "iva": _buscar(r"IVA\s+[\d.,]+%\s+([\d.,]+)", _a_float),
        "total": _buscar(r"VR\.? TOTAL FACTURA COP\s+([\d.,]+)", _a_float),
    }


def parsear_pdf_postobon(archivo):
    """archivo: ruta o file-like (lo que acepte pdfplumber.open, incluido el stream que
    entrega Flask desde un <input type=file>). Devuelve encabezado + totales impresos +
    una línea por producto, cada una con el producto ya resuelto si su código está en
    CodigoPostobon, o sin resolver (para que el usuario lo asigne) si es nuevo."""
    lineas = []
    texto_paginas = []
    tablas = []
    with pdfplumber.open(archivo) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""
            texto_paginas.append(texto)
            tablas.extend(pagina.extract_tables())
            palabras = pagina.extract_words(use_text_flow=False, keep_blank_chars=False)
            lineas.extend(parsear_lineas_desde_palabras(palabras))

    texto_completo = "\n".join(texto_paginas)
    descripciones = _descripciones_por_codigo(texto_completo)
    encabezado = parsear_encabezado_desde_texto(texto_completo, tablas)
    totales = parsear_totales_footer(texto_completo)

    for linea in lineas:
        linea["descripcion"] = descripciones.get(linea["codigo"], "")
        producto = buscar_producto_por_codigo(linea["codigo"])
        linea["producto_id"] = producto.id if producto else None
        linea["producto_nombre"] = producto.nombre if producto else None

    return {
        "numero_factura": encabezado["numero_factura"],
        "fecha": encabezado["fecha"],
        "totales_factura": totales,
        "lineas": lineas,
    }
