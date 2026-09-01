from models import CodigoPostobon, Producto


def buscar_producto_por_codigo(codigo):
    """Producto ya confirmado para este código de referencia de Postobón, o None si es
    un código nuevo que todavía no se ha asignado."""
    mapeo = CodigoPostobon.query.filter_by(codigo=codigo.strip()).first()
    return mapeo.producto if mapeo else None


def listar_codigos():
    return (
        CodigoPostobon.query.join(Producto)
        .order_by(Producto.nombre, CodigoPostobon.codigo)
        .all()
    )
