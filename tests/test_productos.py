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


def test_editar_producto_recalcula_precio_por_unidad_si_solo_cambian_las_unidades_por_caja(client):
    # precio de caja se deja igual (45000) pero las unidades por caja bajan de 15 a 12 --
    # el precio por unidad debe subir de 3000 a 3750, aunque el de caja no haya cambiado.
    crear_producto(client, nombre="Pet 1,5 Lts Gaseosa", precio_caja="45000", unidades_por_caja="15")
    from models import Producto

    p = Producto.query.filter_by(nombre="Pet 1,5 Lts Gaseosa").first()
    assert p.precio_actual() == 3000

    client.post(
        f"/productos/{p.id}/editar",
        data={
            "nombre": "Pet 1,5 Lts Gaseosa",
            "categoria": "Gaseosa",
            "unidades_por_caja": "12",
            "maneja_cajas": "on",
            "maneja_unidades": "on",
            "precio_venta_caja": "45000",
            "tasa_descuento_referencia": "0",
        },
        follow_redirects=True,
    )

    assert p.precio_actual() == 3750  # 45000 / 12
    assert p.precio_caja_actual() == 45000


def test_eliminar_producto_sin_movimientos_lo_borra(client):
    crear_producto(client)
    from models import Producto

    p = Producto.query.filter_by(nombre="Coca-Cola 1.5L").first()
    producto_id = p.id

    r = client.post(f"/productos/{producto_id}/eliminar", follow_redirects=True)
    assert r.status_code == 200
    assert Producto.query.get(producto_id) is None


def test_eliminar_producto_con_movimientos_se_bloquea(client, db):
    crear_producto(client)
    from datetime import date
    from models import Producto, Compra, CompraDetalle

    p = Producto.query.filter_by(nombre="Coca-Cola 1.5L").first()
    producto_id = p.id

    compra = Compra(fecha=date(2026, 8, 1))
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=producto_id, cantidad_comprada_unidades=60,
            costo_linea=180000, tasa_descuento_aplicada=5.0,
        )
    )
    db.session.commit()

    r = client.post(f"/productos/{producto_id}/eliminar", follow_redirects=True)
    assert r.status_code == 200
    # sigue existiendo -- no se pudo eliminar por tener movimientos
    assert Producto.query.get(producto_id) is not None


def test_inventario_muestra_cajas_y_unidades_sueltas_no_total(client, db):
    crear_producto(client, unidades_por_caja="6")
    from datetime import date
    from models import Producto, Compra, CompraDetalle

    p = Producto.query.filter_by(nombre="Coca-Cola 1.5L").first()
    compra = Compra(fecha=date(2026, 8, 1))
    db.session.add(compra)
    db.session.flush()
    db.session.add(
        CompraDetalle(
            compra_id=compra.id, producto_id=p.id, cantidad_comprada_unidades=15,
            costo_linea=45000, tasa_descuento_aplicada=0.0,
        )
    )
    db.session.commit()

    r = client.get("/productos/inventario")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Cajas" in body and "Unidades sueltas" in body
    assert "Stock (unidades)" not in body
    # 15 unidades = 2 cajas + 3 sueltas (6 u/caja)
    assert ">2<" in body
    assert ">3<" in body
