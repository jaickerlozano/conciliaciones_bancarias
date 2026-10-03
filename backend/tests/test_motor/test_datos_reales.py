"""Regresión contra los archivos reales de la Comunidad Edificio Cinema.

El criterio de éxito del motor: reproducir las conciliaciones que el cliente hizo a mano.
"""

import pytest

from motor.conciliacion import conciliar
from motor.dominio import Periodo, TipoPartida
from motor.parsers.cartolas import ErrorCartola, leer_cartola
from motor.parsers.conciliacion_cliente import leer_conciliacion_cliente
from motor.parsers.libros import leer_libro

pytestmark = pytest.mark.datos_reales

PLANILLA_CONCILIACION = "CONCILIACIÓN  MENSUAL CINEMA.xlsm"


@pytest.fixture(scope="module")
def ingresos(datos):
    return leer_libro(datos / "listado ingresos CINEMA2.xlsx", TipoPartida.INGRESO)


@pytest.fixture(scope="module")
def egresos(datos):
    return leer_libro(datos / "emitir egresos CINEMA.xlsm", TipoPartida.EGRESO)


def test_totales_mensuales_coinciden_con_la_conciliacion_del_cliente(datos, ingresos, egresos):
    hojas = {1: "ENERO'26", 2: "FEBRERO'26", 3: "MARZO'26", 4: "ABRIL´26", 5: "MAYO´26"}
    for mes, hoja in hojas.items():
        cliente = leer_conciliacion_cliente(datos / PLANILLA_CONCILIACION, hoja)
        periodo = Periodo(2026, mes)
        assert ingresos.total(periodo) == cliente.total_ingresos, hoja
        # el cliente suma egresos con decimales (UF); nosotros redondeamos cada partida
        assert abs(egresos.total(periodo) - cliente.total_egresos) <= 1, hoja


def test_detecta_fecha_con_anio_erroneo(ingresos):
    assert any("18/08/2226" in a for a in ingresos.advertencias)


def test_cartola_santander_mayo(datos):
    c = leer_cartola(datos / "cartola_mayo_2026.pdf")
    assert (c.numero, c.cuenta) == ("306", "0-000-03-81745-8")
    assert (c.saldo_inicial, c.saldo_final) == (4_180_917, 5_164_850)
    assert len(c.movimientos) == 31
    assert c.advertencias == []
    transf = c.movimientos[1]
    assert (transf.monto, transf.es_cargo, transf.documento) == (403_161, False, "1304726")
    cheque = c.movimientos[5]
    assert (cheque.monto, cheque.es_cargo, cheque.documento) == (220_619, True, "1587125")


def test_cartola_santander_febrero_dos_paginas(datos):
    c = leer_cartola(datos / "cartola_febrero_2026.pdf")
    assert c.advertencias == []  # saldo inicial + movimientos == saldo final


@pytest.mark.parametrize("mes", ["enero", "marzo", "abril"])
def test_formatos_no_soportados_fallan_con_mensaje_claro(datos, mes):
    with pytest.raises(ErrorCartola, match="No se reconoce el formato"):
        leer_cartola(datos / f"cartola_{mes}_2026.pdf")


def test_reproduce_conciliacion_mayo_2026(datos, ingresos, egresos):
    apertura = leer_conciliacion_cliente(datos / PLANILLA_CONCILIACION, "ABRIL´26")
    esperado = leer_conciliacion_cliente(datos / PLANILLA_CONCILIACION, "MAYO´26")
    cartola = leer_cartola(datos / "cartola_mayo_2026.pdf")
    periodo = Periodo(2026, 5)

    r = conciliar(
        periodo,
        apertura.como_apertura(),
        ingresos.partidas(periodo),
        egresos.partidas(periodo),
        cartola,
    )

    assert r.saldo_registro == esperado.saldo_registro
    assert sorted(p.comprobante for p in r.cheques_pendientes) == sorted(
        p.comprobante for p in esperado.cheques_pendientes
    )
    assert sorted(p.comprobante for p in r.depositos_pendientes) == sorted(
        p.comprobante for p in esperado.depositos_pendientes
    )
    assert r.movimientos_no_contabilizados == []
    assert r.saldo_banco == esperado.saldo_banco
    assert r.diferencia == 0
    assert r.advertencias == []


def test_febrero_2026_detecta_traslape_de_cartolas(datos, ingresos, egresos):
    """La cartola de febrero (desde 30/01) repite dos movimientos del 02/02 que el cliente ya
    había conciliado en enero. El motor debe avisarlo, y la diferencia es exactamente eso."""
    apertura = leer_conciliacion_cliente(datos / PLANILLA_CONCILIACION, "ENERO'26")
    cartola = leer_cartola(datos / "cartola_febrero_2026.pdf")
    periodo = Periodo(2026, 2)

    r = conciliar(
        periodo,
        apertura.como_apertura(),
        ingresos.partidas(periodo),
        egresos.partidas(periodo),
        cartola,
    )

    assert any("no coincide con el saldo final" in a for a in r.advertencias)
    assert r.diferencia == -(351_821 - 66_010)


def test_advertencias_por_periodo(ingresos, egresos):
    assert any("18/08/2226" in a for a in ingresos.advertencias_de(Periodo(2026, 8)))
    assert ingresos.advertencias_de(Periodo(2026, 5)) == []
    assert any("1364" in a for a in egresos.advertencias_de(Periodo(2026, 3)))  # decimales UF
