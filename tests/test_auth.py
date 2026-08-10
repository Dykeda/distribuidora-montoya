import pytest


@pytest.fixture
def client(app):
    return app.test_client()


def test_ruta_protegida_sin_sesion_redirige_a_login(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_login_con_password_correcto_da_acceso(client, app):
    r = client.post(
        "/login", data={"password": app.config["APP_PASSWORD"]}, follow_redirects=True
    )
    assert r.status_code == 200
    assert client.get("/").status_code == 200


def test_login_con_password_incorrecto_no_da_acceso(client):
    r = client.post("/login", data={"password": "incorrecta"}, follow_redirects=True)
    assert r.status_code == 200
    assert "Contraseña incorrecta" in r.get_data(as_text=True)
    assert client.get("/", follow_redirects=False).status_code == 302


def test_logout_cierra_la_sesion(client, app):
    client.post("/login", data={"password": app.config["APP_PASSWORD"]})
    assert client.get("/").status_code == 200
    client.get("/logout")
    assert client.get("/", follow_redirects=False).status_code == 302
