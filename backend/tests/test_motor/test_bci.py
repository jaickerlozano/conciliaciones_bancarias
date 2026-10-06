"""Cartola oficial BCI en PDF (Comunidad Edificio Bustos, cuenta corriente BCI).

Usa los archivos reales del cliente (no versionados); se omite si no están.
"""

from __future__ import annotations

from datetime import date

import pytest

from motor.parsers.cartolas import leer_cartola
from motor.parsers.cartolas.bci_pdf import BciPDFOficial

pytestmark = pytest.mark.datos_reales

# archivo, desde, hasta, saldo inicial, saldo final, total cargos, total abonos, nº movimientos
CASOS = [
    (
        "cartola_junio_2026.pdf",
        date(2026, 5, 29),
        date(2026, 6, 30),
        33_388_540,
        34_102_392,
        5_730_742,
        6_444_594,
        62,
    ),
    (
        "cartola_julio_2026.pdf",
        date(2026, 6, 30),
        date(2026, 7, 31),
        34_102_392,
        31_549_406,
        8_950_234,
        6_397_248,
        67,
    ),
    (
        "cartola_agosto_2026.pdf",
        date(2026, 7, 31),
        date(2026, 8, 31),
        31_549_406,
        30_526_555,
        7_870_795,
        6_847_944,
        64,
    ),
]


@pytest.mark.parametrize(
    ("archivo", "desde", "hasta", "inicial", "final", "cargos", "abonos", "cantidad"), CASOS
)
def test_lee_cartola_bci(
    datos_bustos, archivo, desde, hasta, inicial, final, cargos, abonos, cantidad
):
    ruta = datos_bustos / archivo
    assert BciPDFOficial.puede_leer(ruta)
    cartola = leer_cartola(ruta)
    assert cartola.banco == "BCI"
    assert cartola.cuenta == "29845203"
    assert (cartola.desde, cartola.hasta) == (desde, hasta)
    assert (cartola.saldo_inicial, cartola.saldo_final) == (inicial, final)
    assert sum(m.monto for m in cartola.movimientos if m.es_cargo) == cargos
    assert sum(m.monto for m in cartola.movimientos if not m.es_cargo) == abonos
    assert len(cartola.movimientos) == cantidad
    assert cartola.advertencias == []


def test_bci_cheque_y_transferencia(datos_bustos):
    cartola = leer_cartola(datos_bustos / "cartola_junio_2026.pdf")
    cheque = next(m for m in cartola.movimientos if m.documento == "5840593")
    assert cheque.es_cargo
    assert cheque.monto == 692_936
    assert cheque.fecha == date(2026, 6, 2)
    assert cheque.descripcion.startswith("CHEQUE COBRADO")

    primero = cartola.movimientos[0]
    assert not primero.es_cargo
    assert primero.monto == 100_000
    assert primero.fecha == date(2026, 6, 1)
    assert primero.documento == ""
    assert primero.descripcion.startswith("TRANSFER DE")
    assert primero.sucursal == "OF CENTRA"

    # el RUT dentro de la descripción no se confunde con el nº de documento
    abono_terceros = next(m for m in cartola.movimientos if m.descripcion.startswith("ABONO TERC"))
    assert abono_terceros.documento == ""
    assert not abono_terceros.es_cargo


def test_bci_no_reclama_cartola_santander(datos):
    ruta = datos / "cartola_mayo_2026.pdf"
    if not ruta.is_file():
        pytest.skip(f"No está {ruta.name}")
    assert not BciPDFOficial.puede_leer(ruta)
