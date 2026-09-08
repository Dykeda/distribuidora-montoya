def bruto_linea(detalle):
    """Reconstruye el valor bruto (antes de descuento) de una línea de compra a partir
    del costo neto guardado y la tasa aplicada -- para poder mostrar Subtotal/Descuento/
    Total (o sumarlos por proveedor/período) sin tener que guardar el bruto aparte."""
    if detalle.tasa_descuento_aplicada >= 100:
        return detalle.costo_linea
    return round(detalle.costo_linea / (1 - detalle.tasa_descuento_aplicada / 100))


def total_a_pagar(compra):
    """Costo neto + IVA de todas las líneas -- el "Total a pagar" real de la compra,
    igual al que muestra la factura impresa."""
    return sum(d.costo_linea + d.valor_iva for d in compra.detalles)


def es_postobon(compra):
    """Nulo (compras viejas o sin proveedor elegido) se trata como Postobón -- mismo
    criterio que usan routes/compras.py y services/postobon.py."""
    return compra.proveedor.es_postobon if compra.proveedor else True
