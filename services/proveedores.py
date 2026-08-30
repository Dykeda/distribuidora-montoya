from datetime import date

from extensions import db
from models import Proveedor, Compra, CompraDetalle, Producto
from services.compras import bruto_linea
from services.inventario import cajas_y_unidades

# Fecha de arranque para sumas "históricas" (todo lo que haya, no acotado a un mes).
DESDE_SIEMPRE = date(2000, 1, 1)


def listar_proveedores(solo_activos=True):
    query = Proveedor.query
    if solo_activos:
        query = query.filter_by(activo=True)
    return query.order_by(Proveedor.nombre).all()


def proveedor_postobon():
    """Proveedor "Postobón" (es_postobon=True) -- se crea solo si todavía no existe. Es el
    valor por defecto de Compra.proveedor_id (ver models.py), para que las compras
    antiguas o creadas sin especificar proveedor (pruebas incluidas) sigan asumiéndose
    como Postobón, el caso normal de este negocio."""
    proveedor = Proveedor.query.filter_by(nombre="Postobón").first()
    if proveedor is None:
        proveedor = Proveedor(nombre="Postobón", es_postobon=True)
        db.session.add(proveedor)
        db.session.flush()
    return proveedor


def resumen_proveedores():
    """Para cada proveedor activo: cuántas compras tiene -- para el listado."""
    return [{"proveedor": p, "cantidad_compras": len(p.compras)} for p in listar_proveedores()]


def resumen_compras_proveedor(proveedor_id, fecha_inicio, fecha_fin):
    """Compras hechas a este proveedor en el período, agrupadas por producto: cuánto se
    compró (cajas/unidades), cuánto se pagó y cuánto fue el descuento (el bruto
    reconstruido de cada línea menos lo pagado) -- mismo cálculo que se ve en el detalle
    de una compra individual, pero sumado por producto a lo largo de todas las compras
    del período."""
    detalles = (
        CompraDetalle.query.join(Compra)
        .join(Producto)
        .filter(Compra.proveedor_id == proveedor_id)
        .filter(Compra.fecha >= fecha_inicio, Compra.fecha <= fecha_fin)
        .all()
    )

    por_producto = {}
    for d in detalles:
        fila = por_producto.setdefault(d.producto_id, {
            "producto": d.producto, "cantidad_unidades": 0, "costo_pagado": 0, "descuento": 0,
        })
        fila["cantidad_unidades"] += d.cantidad_comprada_unidades
        fila["costo_pagado"] += d.costo_linea
        fila["descuento"] += bruto_linea(d) - d.costo_linea

    filas = []
    for fila in por_producto.values():
        cajas, unidades_sueltas = cajas_y_unidades(fila["producto"], fila["cantidad_unidades"])
        filas.append({**fila, "cajas": cajas, "unidades_sueltas": unidades_sueltas})
    filas.sort(key=lambda f: f["producto"].nombre)
    return filas


def total_descuento_proveedor(proveedor_id, fecha_inicio, fecha_fin):
    """Suma del descuento (bruto reconstruido menos lo pagado) de todas las líneas de
    compra de este proveedor en el período -- sin desglosar por producto, para las cards
    de "este mes" y "acumulado histórico"."""
    detalles = (
        CompraDetalle.query.join(Compra)
        .filter(Compra.proveedor_id == proveedor_id)
        .filter(Compra.fecha >= fecha_inicio, Compra.fecha <= fecha_fin)
        .all()
    )
    return round(sum(bruto_linea(d) - d.costo_linea for d in detalles))
