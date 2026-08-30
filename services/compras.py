def bruto_linea(detalle):
    """Reconstruye el valor bruto (antes de descuento) de una línea de compra a partir
    del costo neto guardado y la tasa aplicada -- para poder mostrar Subtotal/Descuento/
    Total (o sumarlos por proveedor/período) sin tener que guardar el bruto aparte."""
    if detalle.tasa_descuento_aplicada >= 100:
        return detalle.costo_linea
    return round(detalle.costo_linea / (1 - detalle.tasa_descuento_aplicada / 100))
