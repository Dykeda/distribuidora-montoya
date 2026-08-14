from models import Cliente
from services.cartera import total_pendiente


def listar_clientes(solo_activos=True):
    query = Cliente.query
    if solo_activos:
        query = query.filter_by(activo=True)
    return query.order_by(Cliente.nombre).all()


def resumen_clientes():
    """Para cada cliente activo: cuántas facturas tiene y cuánto le queda pendiente por
    pagar — así se ve de un vistazo si un cliente tiene más de una factura."""
    resultado = []
    for c in listar_clientes():
        resultado.append({
            "cliente": c,
            "cantidad_facturas": len(c.facturas),
            "total_pendiente": total_pendiente(cliente_id=c.id),
        })
    return resultado
