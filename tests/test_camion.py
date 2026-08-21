from datetime import date

import pytest

from models import (
    Producto,
    ProductoPrecio,
    SalidaCamion,
    SalidaCamionDetalle,
    RetornoCamion,
    RetornoCamionDetalle,
    RecargaCamion,
    RecargaCamionDetalle,
)
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
    # 26 unidades cargadas, se vende todo (retorno 0) -> venta implicita = 26*3000 = 78000
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=26))
    db.session.commit()

    r = client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={
            "fecha": HOY, "notas": "",
            f"regreso_cajas_{coca.id}": "0", f"regreso_unidades_{coca.id}": "0",
            "efectivo_contado": "75000", "monedas_contado": "3500",
            "nuevos_creditos": "5000",
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
    # esperado = 78000 + 5000 (nuevos creditos) = 83000; venta total = 78000 -> sobraron 5000
    assert "Sobraron" in body
    assert "5,000" in body


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
            "gasto_en_ruta": "8000",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    r = client.get(f"/camion/{salida.id}")
    body = r.get_data(as_text=True)
    assert "Cuadre de caja" in body
    # esperado = 78000 - 8000 (gasto) = 70000; venta total = 78000 -> faltan 8000
    assert "Faltan" in body
    assert "8,000" in body


def test_editar_retorno_ya_registrado_actualiza_cantidades_y_cuadre(db, client):
    coca = crear_producto(db, unidades_por_caja=6, precio=3000)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=60))
    db.session.commit()

    client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={"fecha": HOY, "notas": "", f"regreso_cajas_{coca.id}": "3", f"regreso_unidades_{coca.id}": "0"},
        follow_redirects=True,
    )
    retorno = RetornoCamion.query.filter_by(salida_id=salida.id).first()
    assert retorno.detalles[0].cantidad_unidades == 18  # 3 cajas * 6

    # se dan cuenta que en realidad regresaron 5 cajas, no 3 -- corrigen sin borrar nada
    r = client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={
            "fecha": HOY, "notas": "corregido",
            f"regreso_cajas_{coca.id}": "5", f"regreso_unidades_{coca.id}": "0",
            "efectivo_contado": "10000", "monedas_contado": "500",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    retorno_actualizado = RetornoCamion.query.filter_by(salida_id=salida.id).first()
    assert retorno_actualizado.id == retorno.id  # mismo retorno, no uno nuevo
    assert len(retorno_actualizado.detalles) == 1
    assert retorno_actualizado.detalles[0].cantidad_unidades == 30  # 5 cajas * 6
    assert retorno_actualizado.efectivo_contado == 10000
    assert retorno_actualizado.monedas_contado == 500
    assert calcular_stock(coca.id) == -30  # -60 salio + 30 regreso


def test_agregar_recarga_a_ruta_ya_cerrada_ya_no_se_bloquea(db, client):
    coca = crear_producto(db, unidades_por_caja=6, precio=3000)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=60))
    db.session.commit()

    client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={"fecha": HOY, "notas": "", f"regreso_cajas_{coca.id}": "0", f"regreso_unidades_{coca.id}": "0"},
        follow_redirects=True,
    )

    r = client.post(
        f"/camion/recarga/nueva/{salida.id}",
        data={"fecha": HOY, "notas": "", "producto_id[]": [str(coca.id)], "cajas[]": ["1"], "unidades[]": ["0"]},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "Recarga registrada" in r.get_data(as_text=True)


def test_eliminar_recarga(db, client):
    coca = crear_producto(db, unidades_por_caja=6, precio=3000)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=60))
    db.session.commit()

    recarga = RecargaCamion(salida_id=salida.id, fecha=date(2026, 8, 1))
    db.session.add(recarga)
    db.session.flush()
    db.session.add(RecargaCamionDetalle(recarga_id=recarga.id, producto_id=coca.id, cantidad_unidades=6))
    db.session.commit()

    assert calcular_stock(coca.id) == -66  # -60 salida - 6 recarga

    r = client.post(f"/camion/recarga/{recarga.id}/eliminar", follow_redirects=True)
    assert r.status_code == 200
    assert RecargaCamion.query.get(recarga.id) is None
    assert calcular_stock(coca.id) == -60


def test_agregar_producto_a_la_carga(db, client):
    coca = crear_producto(db, unidades_por_caja=6, precio=3000)
    sprite = crear_producto(db, nombre="Sprite 1.5L", unidades_por_caja=6, precio=2500)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=60))
    db.session.commit()

    r = client.post(
        f"/camion/{salida.id}/carga/nueva",
        data={"producto_id": str(sprite.id), "cajas": "2", "unidades": "0"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert calcular_stock(sprite.id) == -12  # 2 cajas * 6 salieron


def test_editar_linea_de_carga(db, client):
    coca = crear_producto(db, unidades_por_caja=6, precio=3000)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=60))
    db.session.commit()
    detalle = salida.detalles[0]

    r = client.post(
        f"/camion/{salida.id}/carga/{detalle.id}/editar",
        data={"cajas": "8", "unidades": "0"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert calcular_stock(coca.id) == -48  # 8 cajas * 6


def test_editar_linea_de_carga_no_permite_menos_de_lo_ya_regresado(db, client):
    coca = crear_producto(db, unidades_por_caja=6, precio=3000)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=60))
    db.session.commit()
    detalle = salida.detalles[0]

    client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={"fecha": HOY, "notas": "", f"regreso_cajas_{coca.id}": "5", f"regreso_unidades_{coca.id}": "0"},
        follow_redirects=True,
    )  # regresaron 30 (5 cajas)

    # intentan bajar la carga a 3 cajas (18) -- menos de lo ya regresado (30) -> debe bloquear
    r = client.post(
        f"/camion/{salida.id}/carga/{detalle.id}/editar",
        data={"cajas": "3", "unidades": "0"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "Corrige primero el retorno" in r.get_data(as_text=True)

    actualizado = SalidaCamionDetalle.query.get(detalle.id)
    assert actualizado.cantidad_unidades == 60  # no cambió


def test_eliminar_linea_de_carga(db, client):
    coca = crear_producto(db, unidades_por_caja=6, precio=3000)
    agua = crear_producto(db, nombre="Agua Cristal", unidades_por_caja=12, precio=2000)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=60))
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=agua.id, cantidad_unidades=24))
    db.session.commit()
    detalle_coca = next(d for d in salida.detalles if d.producto_id == coca.id)

    r = client.post(f"/camion/{salida.id}/carga/{detalle_coca.id}/eliminar", follow_redirects=True)
    assert r.status_code == 200
    assert calcular_stock(coca.id) == 0
    assert calcular_stock(agua.id) == -24


def test_lista_de_camion_muestra_acceso_directo_al_cuadre_segun_estado(db, client):
    coca = crear_producto(db, unidades_por_caja=6, precio=3000)

    salida_abierta = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida_abierta)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida_abierta.id, producto_id=coca.id, cantidad_unidades=12))

    salida_cerrada = SalidaCamion(fecha=date(2026, 8, 2))
    db.session.add(salida_cerrada)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida_cerrada.id, producto_id=coca.id, cantidad_unidades=12))
    db.session.commit()

    client.post(
        f"/camion/retorno/nueva/{salida_cerrada.id}",
        data={"fecha": HOY, "notas": "", f"regreso_cajas_{coca.id}": "0", f"regreso_unidades_{coca.id}": "0"},
        follow_redirects=True,
    )

    r = client.get("/camion/?anio=2026&mes=8")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert f"/camion/retorno/nueva/{salida_abierta.id}" in body
    assert f"/camion/retorno/nueva/{salida_cerrada.id}" in body
    assert "Editar cuadre de caja" in body
    assert "Registrar retorno" in body


def test_cuadre_de_caja_incluye_gasto_creditos_pagados_y_nuevos_creditos(db, client):
    coca = crear_producto(db, unidades_por_caja=6, precio=3000)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    # 26 unidades cargadas, se vende todo (retorno 0) -> venta implicita = 26*3000 = 78000
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=26))
    db.session.commit()

    r = client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={
            "fecha": HOY, "notas": "",
            f"regreso_cajas_{coca.id}": "0", f"regreso_unidades_{coca.id}": "0",
            "efectivo_contado": "70000", "monedas_contado": "0",
            "gasto_en_ruta": "5000", "creditos_pagados": "10000", "nuevos_creditos": "13000",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    retorno = RetornoCamion.query.filter_by(salida_id=salida.id).first()
    assert retorno.gasto_en_ruta == 5000
    assert retorno.creditos_pagados == 10000
    assert retorno.nuevos_creditos == 13000

    r = client.get(f"/camion/{salida.id}")
    body = r.get_data(as_text=True)
    # esperado = 78000 - 5000 (gasto) + 13000 (nuevos creditos) + 10000 (creditos pagados) = 96000
    # venta total = 78000 + 10000 (creditos pagados) = 88000
    # diferencia = 96000 - 88000 = 8000 -> sobraron
    assert "96,000" in body
    assert "88,000" in body
    assert "Sobraron" in body
    assert "8,000" in body


def test_editar_retorno_permite_ajustar_gasto_en_ruta(db, client):
    coca = crear_producto(db, unidades_por_caja=6, precio=3000)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=26))
    db.session.commit()

    client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={
            "fecha": HOY, "notas": "",
            f"regreso_cajas_{coca.id}": "0", f"regreso_unidades_{coca.id}": "0",
            "efectivo_contado": "78000", "monedas_contado": "0",
        },
        follow_redirects=True,
    )

    r = client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={
            "fecha": HOY, "notas": "",
            f"regreso_cajas_{coca.id}": "0", f"regreso_unidades_{coca.id}": "0",
            "efectivo_contado": "78000", "monedas_contado": "0",
            "gasto_en_ruta": "8000",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    r = client.get(f"/camion/{salida.id}")
    body = r.get_data(as_text=True)
    # esperado = 78000 - 8000 (gasto) = 70000; venta total sigue en 78000 -> faltan 8000
    assert "Faltan" in body
    assert "8,000" in body


def test_cuadre_muestra_venta_total_sumando_creditos_y_restando_gasto(db, client):
    coca = crear_producto(db, unidades_por_caja=6, precio=3000)
    salida = SalidaCamion(fecha=date(2026, 8, 1))
    db.session.add(salida)
    db.session.flush()
    # 26 unidades cargadas, se vende todo (retorno 0) -> venta implicita = 26*3000 = 78000
    db.session.add(SalidaCamionDetalle(salida_id=salida.id, producto_id=coca.id, cantidad_unidades=26))
    db.session.commit()

    client.post(
        f"/camion/retorno/nueva/{salida.id}",
        data={
            "fecha": HOY, "notas": "",
            f"regreso_cajas_{coca.id}": "0", f"regreso_unidades_{coca.id}": "0",
            "efectivo_contado": "70000", "monedas_contado": "0",
            "gasto_en_ruta": "5000", "creditos_pagados": "10000", "nuevos_creditos": "13000",
        },
        follow_redirects=True,
    )

    r = client.get(f"/camion/{salida.id}")
    body = r.get_data(as_text=True)
    # venta total = 78000 + 10000 (creditos pagados) = 88000
    assert "Venta total" in body
    assert "88,000" in body
