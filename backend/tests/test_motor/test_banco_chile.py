"""Cartola oficial Banco de Chile en PDF (Comunidad Edificio Monseñor Eyzaguirre).

Los tests `datos_reales` usan el archivo del cliente (no versionado) y se omiten si no está.
"""

from __future__ import annotations

from datetime import date

import pytest

from motor.parsers.cartolas import ErrorCartola, leer_cartola
from motor.parsers.cartolas.banco_chile_pdf import BancoChilePDF, fecha_dia_mes

CARTOLA = "cartola_banco_chile.pdf"


@pytest.mark.parametrize(
    ("texto", "desde", "hasta", "esperado"),
    [
        ("29/09", date(2023, 9, 29), date(2023, 10, 31), date(2023, 9, 29)),
        ("31/10", date(2023, 9, 29), date(2023, 10, 31), date(2023, 10, 31)),
        # período que cruza el año: diciembre es del año de inicio, enero del siguiente
        ("30/12", date(2025, 12, 30), date(2026, 1, 31), date(2025, 12, 30)),
        ("02/01", date(2025, 12, 30), date(2026, 1, 31), date(2026, 1, 2)),
    ],
)
def test_fecha_dia_mes(texto, desde, hasta, esperado):
    assert fecha_dia_mes(texto, desde, hasta) == esperado


def test_fecha_dia_mes_fuera_del_periodo():
    with pytest.raises(ErrorCartola, match="fuera del período"):
        fecha_dia_mes("15/03", date(2023, 9, 29), date(2023, 10, 31))


@pytest.mark.datos_reales
def test_lee_cartola_banco_chile(datos_monsenor):
    ruta = datos_monsenor / CARTOLA
    assert BancoChilePDF.puede_leer(ruta)
    cartola = leer_cartola(ruta)
    assert cartola.banco == "Banco de Chile"
    assert cartola.cuenta == "50579801"
    assert cartola.numero == "10"
    assert (cartola.desde, cartola.hasta) == (date(2023, 9, 29), date(2023, 10, 31))
    assert (cartola.saldo_inicial, cartola.saldo_final) == (6_876_193, 15_688_242)
    assert len(cartola.movimientos) == 162
    # resumen: cheques 6.455.626 + otros cargos 7.839.644; depósitos 1.506.247 + otros abonos
    # 21.601.072
    assert sum(m.monto for m in cartola.movimientos if m.es_cargo) == 14_295_270
    assert sum(m.monto for m in cartola.movimientos if not m.es_cargo) == 23_107_319
    assert all(m.monto > 0 for m in cartola.movimientos)
    assert cartola.advertencias == []

    cheque = cartola.movimientos[0]
    assert (cheque.fecha, cheque.es_cargo, cheque.monto) == (date(2023, 10, 2), True, 22_866)
    assert cheque.documento == "02962163"
    assert cheque.descripcion == "CHEQUE COBRADO POR OTRO BANCO"
    assert cheque.sucursal == "CENTRAL"

    traspaso = next(m for m in cartola.movimientos if m.descripcion.startswith("TRASPASO DE:"))
    assert not traspaso.es_cargo
    assert traspaso.documento == ""
    assert traspaso.sucursal == "INTERNET"

    pac = next(m for m in cartola.movimientos if m.descripcion.startswith("PAC METROGAS"))
    assert (pac.es_cargo, pac.monto, pac.fecha) == (True, 5_589_923, date(2023, 10, 31))


@pytest.mark.datos_reales
@pytest.mark.parametrize(
    ("fixture", "archivo"),
    [
        ("datos", "cartola_mayo_2026.pdf"),  # Santander
        ("datos_bustos", "cartola_junio_2026.pdf"),  # BCI
        ("datos_general_cordova", "Cartola sept'26 General Cordova.pdf"),  # Scotiabank
    ],
)
def test_banco_chile_no_reclama_otros_bancos(request, fixture, archivo):
    ruta = request.getfixturevalue(fixture) / archivo
    if not ruta.is_file():
        pytest.skip(f"No está {ruta.name}")
    assert not BancoChilePDF.puede_leer(ruta)
