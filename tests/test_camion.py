from datetime import date

import pytest

from models import Producto, ProductoPrecio, SalidaCamion, SalidaCamionDetalle
from services.inventario import calcular_stock

HOY = date.today().isoformat()


@pytest.fixture
def client(app):
    c = app.test_client()
    c.post("/login", data={"password": app.config["APP_PASSWORD"]})
    return c


def crear_producto(db, nombre="Coca-Cola 1.5L", precio=3000, unidades_por_caja=6):
    p = Producto(nombre=nombre, unidades_por_caja=unidades_por_caja, maneja_cajas=True, maneja_unidades=True)
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductoPrecio(producto_id=p.id, precio_venta_unidad=precio, precio_venta_caja=precio * unidades_por_caja, vigente_desde=date(2026, 1, 1)))
    db.session.commit()
    return p


def test_retorno_combina_cajas_y_unidades_sueltas(db, client):
    # Sale 1 caja de 6 = 60 unidades (10 cajas), regresan 3 cajas + 5 unidades sueltas
    coca = crear_producto(db, unidades_por_caja=6)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=60))
    db.session.commit()

    r = client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={
            "fecha": HOY, "notas": "",
            f"regreso_cajas_{coca.id}": "3",
            f"regreso_unidades_{coca.id}": "5",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    from models import RetornoCamion

    retorno = RetornoCamion.query.filter_by(salida_id=salida.id).first()
    assert retorno is not None
    # 3 cajas * 6 + 5 sueltas = 23 unidades regresadas
    assert retorno.detalles[0].cantidad_unidades == 23
    # stock = comprado(0) - salido(60) + regresado(23) = -37 (sin compra previa, solo interesa el movimiento)
    assert calcular_stock(coca.id) == -37


def test_retorno_no_permite_mas_de_lo_cargado(db, client):
    coca = crear_producto(db, unidades_por_caja=6)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=12))
    db.session.commit()

    # 3 cajas * 6 = 18, mas de lo cargado (12) -> debe rechazarse
    r = client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={"fecha": HOY, "notas": "", f"regreso_cajas_{coca.id}": "3", f"regreso_unidades_{coca.id}": "0"},
        follow_redirects=True,
    )
    assert r.status_code == 200

    from models import RetornoCamion

    assert RetornoCamion.query.filter_by(salida_id=salida.id).first() is None


def test_salida_combina_cajas_y_unidades_sueltas(db, client):
    coca = crear_producto(db, unidades_por_caja=6)

    r = client.post(
        "/camion/salida/nueva",
        data={
            "fecha": HOY, "notas": "",
            "producto_id[]": [str(coca.id)],
            "cajas[]": ["4"],
            "unidades[]": ["2"],
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    # 4 cajas * 6 + 2 sueltas = 26 unidades cargadas
    assert calcular_stock(coca.id) == -26


def test_detalle_de_ruta_muestra_cajas_y_unidades_de_carga_y_venta(db, client):
    coca = crear_producto(db, unidades_por_caja=6, precio=3000)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    # 26 unidades cargadas = 4 cajas + 2 sueltas
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=26))
    db.session.commit()

    r = client.get(f"/camion/{salida.id}")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert ">4<" in body and ">2<" in body  # carga: 4 cajas + 2 sueltas

    # se vende todo (retorno en 0)
    r = client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={"fecha": HOY, "notas": "", f"regreso_cajas_{coca.id}": "0", f"regreso_unidades_{coca.id}": "0"},
        follow_redirects=True,
    )
    assert r.status_code == 200

    r = client.get(f"/camion/{salida.id}")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Cajas" in body and "Unidades sueltas" in body
    assert ">78,000<" in body or "78,000" in body  # 26 * 3000


def test_retorno_sin_conteo_de_caja_no_muestra_cuadre(db, client):
    coca = crear_producto(db, unidades_por_caja=6, precio=3000)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=26))
    db.session.commit()

    r = client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={"fecha": HOY, "notas": "", f"regreso_cajas_{coca.id}": "0", f"regreso_unidades_{coca.id}": "0"},
        follow_redirects=True,
    )
    assert r.status_code == 200

    r = client.get(f"/camion/{salida.id}")
    body = r.get_data(as_text=True)
    assert "Cuadre de caja" not in body


def test_retorno_con_conteo_de_caja_muestra_sobrante(db, client):
    coca = crear_producto(db, unidades_por_caja=6, precio=3000)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    # 26 unidades cargadas, se vende todo (retorno 0) -> esperado = 26*3000 = 78000
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=26))
    db.session.commit()

    r = client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={
            "fecha": HOY, "notas": "",
            f"regreso_cajas_{coca.id}": "0", f"regreso_unidades_{coca.id}": "0",
            "efectivo_contado": "75000", "monedas_contado": "3500",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    from models import RetornoCamion

    retorno = RetornoCamion.query.filter_by(salida_id=salida.id).first()
    assert retorno.efectivo_contado == 75000
    assert retorno.monedas_contado == 3500

    r = client.get(f"/camion/{salida.id}")
    body = r.get_data(as_text=True)
    assert "Cuadre de caja" in body
    # esperado 78000, contado 75000+3500=78500 -> sobraron 500
    assert "Sobraron" in body
    assert "500" in body


def test_retorno_con_conteo_de_caja_muestra_faltante(db, client):
    coca = crear_producto(db, unidades_por_caja=6, precio=3000)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=26))
    db.session.commit()

    r = client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={
            "fecha": HOY, "notas": "",
            f"regreso_cajas_{coca.id}": "0", f"regreso_unidades_{coca.id}": "0",
            "efectivo_contado": "70000", "monedas_contado": "0",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    r = client.get(f"/camion/{salida.id}")
    body = r.get_data(as_text=True)
    assert "Cuadre de caja" in body
    # esperado 78000, contado 70000 -> faltan 8000
    assert "Faltan" in body
    assert "8,000" in body
