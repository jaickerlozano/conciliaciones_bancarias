"""Cartolas oficiales Scotiabank en PDF.

- "ESTADO DE CUENTA N° …" (Townhouse General Córdova): `ScotiabankPDF`.
- "ESTADO DE CUENTA CORRIENTE" (Edificio Espacio Lyon): `ScotiabankPDFCuentaCorriente`.

Los tests `datos_reales` usan el archivo del cliente (no versionado) y se omiten si no está.
"""

from __future__ import annotations

from datetime import date

import pytest

from motor.parsers.cartolas import ErrorCartola, leer_cartola
from motor.parsers.cartolas.scotiabank_cc_pdf import (
    ScotiabankPDFCuentaCorriente,
    fecha_abreviada,
    fecha_fila,
)
from motor.parsers.cartolas.scotiabank_pdf import ScotiabankPDF, monto_con_signo

CARTOLA = "Cartola sept'26 General Cordova.pdf"
CARTOLA_LYON = "cartola_espacio_lyon.pdf"


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [("$ -6.867", -6_867), ("$ 1.986.523", 1_986_523), ("-1.396.142", -1_396_142), ("$0", 0)],
)
def test_monto_con_signo(texto, esperado):
    assert monto_con_signo(texto) == esperado


@pytest.mark.datos_reales
def test_lee_cartola_scotiabank(datos_general_cordova):
    ruta = datos_general_cordova / CARTOLA
    assert ScotiabankPDF.puede_leer(ruta)
    cartola = leer_cartola(ruta)
    assert cartola.banco == "Scotiabank"
    assert cartola.cuenta == "000992892528"
    assert cartola.numero == "12"
    assert (cartola.desde, cartola.hasta) == (date(2026, 9, 1), date(2026, 9, 30))
    assert (cartola.saldo_inicial, cartola.saldo_final) == (1_986_523, 2_373_690)
    assert len(cartola.movimientos) == 26
    assert sum(m.monto for m in cartola.movimientos if m.es_cargo) == 2_774_084
    assert sum(m.monto for m in cartola.movimientos if not m.es_cargo) == 3_161_251
    assert all(m.monto > 0 for m in cartola.movimientos)
    assert all(m.documento == "" for m in cartola.movimientos)  # "0" = sin documento
    assert cartola.advertencias == []

    primero = cartola.movimientos[0]
    assert (primero.fecha, primero.es_cargo, primero.monto) == (date(2026, 9, 1), True, 6_867)
    assert primero.descripcion == "COMISION MANTENCION PLAN"
    ultimo = cartola.movimientos[-1]
    assert (ultimo.fecha, ultimo.es_cargo) == (date(2026, 9, 30), False)


@pytest.mark.datos_reales
@pytest.mark.parametrize(
    ("fixture", "archivo"),
    [
        ("datos", "cartola_mayo_2026.pdf"),  # Santander
        ("datos_bustos", "cartola_junio_2026.pdf"),  # BCI
        ("datos_monsenor", "cartola_banco_chile.pdf"),  # Banco de Chile
    ],
)
@pytest.mark.parametrize("parser", [ScotiabankPDF, ScotiabankPDFCuentaCorriente])
def test_scotiabank_no_reclama_otros_bancos(request, fixture, archivo, parser):
    ruta = request.getfixturevalue(fixture) / archivo
    if not ruta.is_file():
        pytest.skip(f"No está {ruta.name}")
    assert not parser.puede_leer(ruta)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [("01/SEP/2026", date(2026, 9, 1)), ("31/dic/2025", date(2025, 12, 31))],
)
def test_fecha_abreviada(texto, esperado):
    assert fecha_abreviada(texto) == esperado


@pytest.mark.parametrize(
    ("dia", "mes", "desde", "hasta", "esperado"),
    [
        ("07", "SEP", date(2026, 9, 1), date(2026, 9, 30), date(2026, 9, 7)),
        ("30", "DIC", date(2025, 12, 15), date(2026, 1, 14), date(2025, 12, 30)),
        ("02", "ENE", date(2025, 12, 15), date(2026, 1, 14), date(2026, 1, 2)),
    ],
)
def test_fecha_fila_deduce_el_anio(dia, mes, desde, hasta, esperado):
    assert fecha_fila(dia, mes, desde, hasta) == esperado


@pytest.mark.parametrize(("dia", "mes"), [("15", "OCT"), ("07", "XYZ")])
def test_fecha_fila_fuera_del_periodo_o_mes_desconocido(dia, mes):
    with pytest.raises(ErrorCartola):
        fecha_fila(dia, mes, date(2026, 9, 1), date(2026, 9, 30))


@pytest.mark.datos_reales
def test_lee_cartola_scotiabank_cuenta_corriente(datos_espacio_lyon):
    ruta = datos_espacio_lyon / CARTOLA_LYON
    cartola = leer_cartola(ruta)
    assert cartola.banco == "Scotiabank"
    assert cartola.cuenta == "0-0099-28968-17"
    assert cartola.numero == "12"
    assert (cartola.desde, cartola.hasta) == (date(2026, 9, 1), date(2026, 9, 30))
    assert (cartola.saldo_inicial, cartola.saldo_final) == (21_770_181, 25_981_169)
    # 120 filas; el "Resumen de Comisiones" del final repite una comisión y no se cuenta
    assert len(cartola.movimientos) == 120
    assert sum(m.monto for m in cartola.movimientos if m.es_cargo) == 17_261_789
    assert sum(m.monto for m in cartola.movimientos if not m.es_cargo) == 21_472_777
    assert all(m.monto > 0 for m in cartola.movimientos)
    assert all(date(2026, 9, 1) <= m.fecha <= date(2026, 9, 30) for m in cartola.movimientos)
    assert cartola.validar() == []
    assert cartola.advertencias == []

    cheques = [m for m in cartola.movimientos if m.descripcion.startswith("CHEQUE PAGADO")]
    assert cheques and all(m.es_cargo and len(m.documento) == 8 for m in cheques)
    transferencias = [m for m in cartola.movimientos if m.descripcion.startswith("TEF")]
    assert transferencias and all(m.documento == "" for m in transferencias)  # "00000000"


@pytest.mark.datos_reales
def test_formatos_scotiabank_no_se_reclaman_entre_si(datos_general_cordova, datos_espacio_lyon):
    general_cordova = datos_general_cordova / CARTOLA
    lyon = datos_espacio_lyon / CARTOLA_LYON
    assert ScotiabankPDFCuentaCorriente.puede_leer(lyon)
    assert not ScotiabankPDF.puede_leer(lyon)
    assert not ScotiabankPDFCuentaCorriente.puede_leer(general_cordova)
