"""Reglas de negocio de la API con datos sintéticos (no requieren archivos del cliente)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.conciliaciones.models import Evento

pytestmark = pytest.mark.django_db


def test_no_se_crea_sin_apertura(api, cuenta):
    r = api.post("/api/conciliaciones/", {"cuenta": cuenta.id, "periodo": "2026-05"})
    assert r.status_code == 400
    assert "importe primero el saldo inicial" in r.json()["detail"]


def test_periodo_invalido(api, cuenta):
    r = api.post("/api/conciliaciones/", {"cuenta": cuenta.id, "periodo": "2026-13"})
    assert r.status_code == 400
    assert "periodo" in r.json()


def test_crear_y_no_duplicar(api, apertura):
    datos = {"cuenta": apertura.cuenta_id, "periodo": "2026-05"}
    r = api.post("/api/conciliaciones/", datos)
    assert r.status_code == 201
    assert r.json()["estado"] == "borrador"
    assert r.json()["resumen"]["saldo_anterior"] == 0  # aún no procesada
    assert api.post("/api/conciliaciones/", datos).status_code == 400


def test_procesar_sin_archivos_dice_cuales_faltan(api, apertura):
    c = api.post("/api/conciliaciones/", {"cuenta": apertura.cuenta_id, "periodo": "2026-05"})
    r = api.post(f"/api/conciliaciones/{c.json()['id']}/procesar/")
    assert r.status_code == 400
    assert "planilla de ingresos" in r.json()["detail"]
    assert "cartola bancaria" in r.json()["detail"]


def test_rechaza_extension_invalida(api, apertura):
    c = api.post("/api/conciliaciones/", {"cuenta": apertura.cuenta_id, "periodo": "2026-05"})
    archivo = SimpleUploadedFile("ingresos.docx", b"hola")
    r = api.post(
        f"/api/conciliaciones/{c.json()['id']}/archivos/",
        {"tipo": "ingresos", "archivo": archivo},
        format="multipart",
    )
    assert r.status_code == 400
    assert ".xlsx" in r.json()["detail"]


def test_mesa_de_trabajo_cruce_manual_cerrar_y_reabrir(api, mayo_procesado):
    url = f"/api/conciliaciones/{mayo_procesado.id}"
    detalle = api.get(f"{url}/").json()
    # sin cruzar: el ingreso queda como depósito pendiente y el abono como no contabilizado,
    # que se compensan; la conciliación cuadra pero hay partidas sueltas
    assert detalle["resumen"]["diferencia"] == 0
    partida = detalle["depositos_pendientes"][0]["id"]
    movimiento = detalle["movimientos_no_contabilizados"][0]["id"]

    r = api.post(f"{url}/cruces/", {"partida": partida, "movimiento": movimiento})
    assert r.status_code == 201
    detalle = r.json()
    assert detalle["depositos_pendientes"] == []
    assert detalle["movimientos_no_contabilizados"] == []
    assert detalle["cruces"][0]["tipo"] == "manual"
    assert detalle["resumen"]["diferencia"] == 0

    # no se puede cruzar dos veces
    r = api.post(f"{url}/cruces/", {"partida": partida, "movimiento": movimiento})
    assert r.status_code == 400

    assert api.post(f"{url}/cerrar/").status_code == 200
    assert api.get(f"{url}/").json()["estado"] == "cerrada"

    # cerrada = inmutable
    cruce = detalle["cruces"][0]["id"]
    assert api.delete(f"{url}/cruces/{cruce}/").status_code == 400

    # el mes siguiente ya se puede crear; mientras exista, mayo no se puede reabrir
    junio = api.post("/api/conciliaciones/", {"cuenta": mayo_procesado.cuenta_id,
                                              "periodo": "2026-06"})  # fmt: skip
    assert junio.status_code == 201
    r = api.post(f"{url}/reabrir/", {"motivo": "error en un depósito"})
    assert r.status_code == 400
    assert api.delete(f"/api/conciliaciones/{junio.json()['id']}/").status_code == 204

    assert api.post(f"{url}/reabrir/", {"motivo": ""}).status_code == 400
    r = api.post(f"{url}/reabrir/", {"motivo": "error en un depósito"})
    assert r.status_code == 200
    assert r.json()["estado"] == "procesada"

    acciones = list(
        Evento.objects.filter(conciliacion=mayo_procesado).values_list("accion", flat=True)
    )
    assert acciones == ["reabierta", "cerrada", "cruce_manual"]


def test_cruce_manual_valida_tipo_y_monto(api, mayo_procesado):
    from apps.conciliaciones.models import Movimiento, OrigenMovimiento

    url = f"/api/conciliaciones/{mayo_procesado.id}"
    partida = mayo_procesado.partidas.get()
    cargo = Movimiento.objects.create(
        conciliacion=mayo_procesado, origen=OrigenMovimiento.PERIODO, fecha="2026-05-20",
        monto=50_000, es_cargo=True,
    )  # fmt: skip
    r = api.post(f"{url}/cruces/", {"partida": partida.id, "movimiento": cargo.id})
    assert r.status_code == 400
    assert "ingreso solo con un abono" in r.json()["detail"]

    abono_distinto = Movimiento.objects.create(
        conciliacion=mayo_procesado, origen=OrigenMovimiento.PERIODO, fecha="2026-05-20",
        monto=49_999, es_cargo=False,
    )  # fmt: skip
    r = api.post(f"{url}/cruces/", {"partida": partida.id, "movimiento": abono_distinto.id})
    assert r.status_code == 400
    assert "no coinciden" in r.json()["detail"]


def test_no_cierra_con_diferencia(api, mayo_procesado):
    mayo_procesado.saldo_banco = 1_000_000  # el banco dice otra cosa
    mayo_procesado.save()
    r = api.post(f"/api/conciliaciones/{mayo_procesado.id}/cerrar/")
    assert r.status_code == 400
    assert "diferencia de -$50.000" in r.json()["detail"]


def test_apertura_manual_debe_cuadrar(api, cuenta):
    url = f"/api/cuentas/{cuenta.id}/apertura-manual/"
    datos = {
        "periodo": "2026-04",
        "saldo_registro": 1_000_000,
        "saldo_banco": 1_000_000 + 80_000 - 50_000 + 300_000,
        "cheques_pendientes": [{"comprobante": 1418, "monto": 80_000, "cheque": "1587144"}],
        "depositos_pendientes": [{"comprobante": 1188, "monto": 50_000, "depto": "31"}],
        "movimientos_no_contabilizados": [{"fecha": "2026-01-06", "monto": 300_000}],
    }
    malo = api.post(url, {**datos, "saldo_banco": 1}, format="json")
    assert malo.status_code == 400
    assert "no cuadra" in malo.json()["detail"]
    assert not cuenta.conciliaciones.exists()  # no quedó nada a medias

    r = api.post(url, datos, format="json")
    assert r.status_code == 201, r.json()
    assert r.json()["estado"] == "importada"
    assert r.json()["resumen"]["diferencia"] == 0
    assert len(r.json()["cheques_pendientes"]) == 1

    # ya se puede crear mayo
    mayo = api.post("/api/conciliaciones/", {"cuenta": cuenta.id, "periodo": "2026-05"})
    assert mayo.status_code == 201


def test_redondeo_limitado_y_registrado(api, mayo_procesado):
    url = f"/api/conciliaciones/{mayo_procesado.id}/redondeo/"
    assert api.post(url, {"monto": 101}).status_code == 400
    r = api.post(url, {"monto": 1})
    assert r.status_code == 200
    assert r.json()["resumen"]["redondeo"] == 1
    assert r.json()["resumen"]["diferencia"] == -1
    assert r.json()["eventos"][0]["accion"] == "redondeo"


def test_filtrar_comunidades(api, cuenta):
    from apps.comunidades.models import Comunidad

    Comunidad.objects.create(nombre="Condominio Los Robles", activa=False)
    nombres = lambda q: [c["nombre"] for c in api.get(f"/api/comunidades/?{q}").json()]  # noqa: E731
    assert nombres("q=robles") == ["Condominio Los Robles"]
    assert nombres("activa=true") == ["Edificio Prueba"]
    assert len(nombres("")) == 2
