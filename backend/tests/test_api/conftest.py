from datetime import date

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.comunidades.models import Banco, Comunidad, CuentaBancaria
from apps.conciliaciones.models import (
    Conciliacion,
    EstadoConciliacion,
    Movimiento,
    OrigenMovimiento,
    OrigenPartida,
    Partida,
    TipoPartida,
)


@pytest.fixture(autouse=True)
def media_temporal(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_user("ana", password="clave-segura-123")


@pytest.fixture
def api(usuario) -> APIClient:
    cliente = APIClient()
    cliente.force_authenticate(usuario)
    return cliente


@pytest.fixture
def cuenta(db) -> CuentaBancaria:
    comunidad = Comunidad.objects.create(nombre="Edificio Prueba")
    return CuentaBancaria.objects.create(comunidad=comunidad, banco=Banco.SANTANDER, numero="123")


@pytest.fixture
def apertura(cuenta) -> Conciliacion:
    """Abril importado: saldo registro 1.000.000, banco 1.000.000, sin pendientes."""
    return Conciliacion.objects.create(
        cuenta=cuenta,
        anio=2026,
        mes=4,
        estado=EstadoConciliacion.IMPORTADA,
        saldo_anterior=1_000_000,
        saldo_banco=1_000_000,
    )


@pytest.fixture
def mayo_procesado(apertura) -> Conciliacion:
    """Mayo armado a mano como si lo hubiera procesado el motor, con un ingreso sin cruzar
    y un abono del banco sin cruzar del mismo monto (para probar el cruce manual)."""
    c = Conciliacion.objects.create(
        cuenta=apertura.cuenta,
        anio=2026,
        mes=5,
        estado=EstadoConciliacion.PROCESADA,
        saldo_anterior=1_000_000,
        total_ingresos=50_000,
        total_egresos=0,
        saldo_banco=1_050_000,
    )
    Partida.objects.create(
        conciliacion=c,
        tipo=TipoPartida.INGRESO,
        origen=OrigenPartida.PERIODO,
        comprobante=1,
        fecha=date(2026, 5, 10),
        monto=50_000,
    )
    Movimiento.objects.create(
        conciliacion=c,
        origen=OrigenMovimiento.PERIODO,
        fecha=date(2026, 5, 12),
        descripcion="Transf. de un vecino",
        monto=50_000,
        es_cargo=False,
    )
    return c
