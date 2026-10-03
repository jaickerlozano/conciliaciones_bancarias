from datetime import date

import pytest

from motor.dominio import Cartola, MovimientoBancario
from motor.parsers.cartolas import ErrorCartola, leer_cartola
from motor.parsers.cartolas.plantilla import escribir_plantilla


def test_ida_y_vuelta(tmp_path):
    original = Cartola(
        "Santander", "0-000-03-81745-8", "", date(2026, 1, 1), date(2026, 1, 31),
        1_000_000, 1_000_000 + 300_000 - 4_365,
        [
            MovimientoBancario(date(2026, 1, 6), "Transf. Fondos desde", 300_000, False),
            MovimientoBancario(date(2026, 1, 6), "Servicio PAC", 4_365, True, "1587026"),
        ],
    )  # fmt: skip
    ruta = tmp_path / "cartola.xlsx"
    escribir_plantilla(ruta, original)
    leida = leer_cartola(ruta)
    assert leida.movimientos == original.movimientos
    assert (leida.saldo_inicial, leida.saldo_final) == (1_000_000, 1_295_635)
    assert leida.advertencias == []


def test_plantilla_vacia_pide_datos(tmp_path):
    ruta = tmp_path / "vacia.xlsx"
    escribir_plantilla(ruta)
    with pytest.raises(ErrorCartola, match="le falta: Banco"):
        leer_cartola(ruta)


def test_avisa_si_no_cuadra(tmp_path):
    c = Cartola("BCI", "1", "", date(2026, 1, 1), date(2026, 1, 31), 100, 999,
                [MovimientoBancario(date(2026, 1, 5), "x", 50, False)])  # fmt: skip
    ruta = tmp_path / "c.xlsx"
    escribir_plantilla(ruta, c)
    assert "no cuadra" in leer_cartola(ruta).advertencias[0]
