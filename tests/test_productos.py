import pytest


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"password": app.config["APP_PASSWORD"]})
    return c


def crear_producto(client, nombre="Coca-Cola 1.5L", unidades_por_caja="6", precio_caja="18000"):
    return client.post(
        "/productos/nuevo",
        data={
            "nombre": nombre,
            "categoria": "Gaseosa",
            "unidades_por_caja": unidades_por_caja,
            "maneja_cajas": "on",
            "maneja_unidades": "on",
            "precio_venta_caja": precio_caja,
        },
        follow_redirects=True,
    )


def test_precio_por_caja_se_guarda_como_precio_por_unidad(client):
    crear_producto(client, precio_caja="18000", unidades_por_caja="6")

    from models import Producto

    p = Producto.query.filter_by(nombre="Coca-Cola 1.5L").first()
    assert p.precio_actual() == 3000  # 18000 / 6


def test_precio_de_caja_mostrado_no_arrastra_el_redondeo_del_precio_unidad(client):
    # 20000 / 12 = 1666.67 -> se redondea a 1667 por unidad, pero el precio de caja
    # mostrado debe seguir siendo el 20000 exacto que se escribió, no 1667*12=20004.
    crear_producto(client, nombre="Agua Crist. Aloe", precio_caja="20000", unidades_por_caja="12")

    from models import Producto

    p = Producto.query.filter_by(nombre="Agua Crist. Aloe").first()
    assert p.precio_actual() == 1667
    assert p.precio_caja_actual() == 20000


def test_editar_producto_recalcula_precio_por_unidad(client):
    crear_producto(client)
    from models import Producto

    p = Producto.query.filter_by(nombre="Coca-Cola 1.5L").first()

    client.post(
        f"/productos/{p.id}/editar",
        data={
            "nombre": "Coca-Cola 1.5L",
            "categoria": "Gaseosa",
            "unidades_por_caja": "6",
            "maneja_cajas": "on",
            "maneja_unidades": "on",
            "precio_venta_caja": "24000",
            "tasa_descuento_referencia": "0",
        },
        follow_redirects=True,
    )

    assert p.precio_actual() == 4000  # 24000 / 6
