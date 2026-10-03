import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_sin_sesion_no_hay_acceso():
    assert APIClient().get("/api/comunidades/").status_code == 403


def test_login_con_csrf_y_logout(usuario):
    cliente = APIClient(enforce_csrf_checks=True)
    cliente.get("/api/auth/csrf/")
    token = cliente.cookies["csrftoken"].value

    sin_token = cliente.post("/api/auth/login/", {"usuario": "ana", "clave": "x"}, format="json")
    assert sin_token.status_code == 403

    malo = cliente.post(
        "/api/auth/login/", {"usuario": "ana", "clave": "mala"}, format="json",
        HTTP_X_CSRFTOKEN=token,
    )  # fmt: skip
    assert malo.status_code == 400
    assert malo.json()["detail"] == "Usuario o clave incorrectos."

    ok = cliente.post(
        "/api/auth/login/", {"usuario": "ana", "clave": "clave-segura-123"}, format="json",
        HTTP_X_CSRFTOKEN=token,
    )  # fmt: skip
    assert ok.status_code == 200
    assert ok.json()["usuario"] == "ana"

    token = cliente.cookies["csrftoken"].value  # Django rota el token al iniciar sesión
    assert cliente.get("/api/auth/yo/").json()["usuario"] == "ana"
    assert cliente.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=token).status_code == 204
    assert cliente.get("/api/auth/yo/").status_code == 403
