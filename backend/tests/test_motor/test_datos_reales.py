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


def test_formato_no_soportado_falla_con_mensaje_claro(datos):
    """Enero es una consulta impresa como trazos vectoriales: no tiene texto que leer."""
    with pytest.raises(ErrorCartola, match="No se reconoce el formato"):
        leer_cartola(datos / "cartola_enero_2026.pdf")


@pytest.mark.parametrize("mes", ["marzo", "abril"])
def test_cartola_oficial_coincide_con_su_transcripcion_a_plantilla(datos, mes):
    """El cliente reemplazó marzo y abril por las cartolas oficiales. Deben calzar con las
    versiones que se habían transcrito a mano a la plantilla estándar."""
    oficial = leer_cartola(datos / f"cartola_{mes}_2026.pdf")
    plantilla = datos / "cartolas_estandar" / f"cartola_{mes}_2026.xlsx"
    if not plantilla.exists():
        pytest.skip("Falta la plantilla estándar transcrita")
    transcrita = leer_cartola(plantilla)
    assert oficial.advertencias == []
    assert (oficial.saldo_inicial, oficial.saldo_final) == (
        transcrita.saldo_inicial,
        transcrita.saldo_final,
    )
    assert sorted((m.monto, m.es_cargo) for m in oficial.movimientos) == sorted(
        (m.monto, m.es_cargo) for m in transcrita.movimientos
    )


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


def test_simulacion_enero_a_mayo_igual_al_cliente(datos):
    """Encadena enero→mayo usando solo los resultados del programa y compara con las hojas
    del cliente. Enero, marzo y abril usan sus cartolas en plantilla estándar."""
    from motor.simular import simular

    estandar = datos / "cartolas_estandar"
    if not estandar.is_dir():
        pytest.skip("Faltan las cartolas en plantilla estándar")
    resultados = simular(
        datos / PLANILLA_CONCILIACION,
        datos / "listado ingresos CINEMA2.xlsx",
        datos / "emitir egresos CINEMA.xlsm",
        {
            Periodo(2026, 1): estandar / "cartola_enero_2026.xlsx",
            Periodo(2026, 2): datos / "cartola_febrero_2026.pdf",
            Periodo(2026, 3): estandar / "cartola_marzo_2026.xlsx",
            Periodo(2026, 4): estandar / "cartola_abril_2026.xlsx",
            Periodo(2026, 5): datos / "cartola_mayo_2026.pdf",
        },
        Periodo(2026, 1),
        Periodo(2026, 5),
    )
    for c in resultados:
        assert c.coincide, (c.periodo, c.diferencias)
        assert c.resultado.cuadra, (c.periodo, c.resultado.diferencia)
    assert len(resultados[1].resultado.movimientos_descartados) == 2  # traslape de febrero


@pytest.fixture(scope="module")
def nunoa_junio(datos_nunoa):
    """Junio 2026 de Ñuñoa Centro desde la hoja de mayo del cliente, sin su "redondeo"."""
    from motor.simular import hoja_del_periodo

    planilla = datos_nunoa / "CONCILIACIÓN  MENSUAL ÑUÑOA CENTRO.xlsm"
    hoja_mayo = hoja_del_periodo(planilla, Periodo(2026, 5))
    assert hoja_mayo is not None
    apertura = leer_conciliacion_cliente(planilla, hoja_mayo).como_apertura()
    junio = Periodo(2026, 6)
    ingresos = leer_libro(datos_nunoa / "listado_ingresos_nunoa_centro.xlsx", TipoPartida.INGRESO)
    egresos = leer_libro(datos_nunoa / "emitir egresos Ñuñoa Centro.xlsm", TipoPartida.EGRESO)
    cartola = leer_cartola(datos_nunoa / "cartola_junio_2026.pdf")
    return conciliar(junio, apertura, ingresos.partidas(junio), egresos.partidas(junio), cartola)


def test_nunoa_junio_2026_cheque_cobrado_por_menos_cuadra_sin_redondeo(nunoa_junio):
    """Ñuñoa Centro (BCI): un cheque de junio se cobró $9.000 menos de lo registrado. El
    cliente lo tapó con un "redondeo"; el programa lo deja como cheque pendiente y cuadra."""
    from motor.dominio import Origen

    r = nunoa_junio
    assert r.redondeo == 0
    assert r.diferencia == 0
    diferencias = [p for p in r.cheques_pendientes if p.origen == Origen.DIFERENCIA]
    assert [p.monto for p in diferencias] == [9_000]


def test_nunoa_junio_2026_deposito_agrupado_de_dos_ingresos_de_mayo(nunoa_junio):
    """El abono de $285.796 del 03/06 es la suma de dos ingresos de mayo (arrastrados como
    depósitos pendientes): se cruza como grupo sugerido y la conciliación sigue cuadrando."""
    from motor.dominio import TipoCruce

    r = nunoa_junio
    agrupados = [c for c in r.cruces if c.movimiento.monto == 285_796 and not c.movimiento.es_cargo]
    assert sorted(c.partida.comprobante for c in agrupados) == [34917, 34918]
    assert all(c.tipo == TipoCruce.AGRUPADO and c.requiere_revision for c in agrupados)
    assert len({c.grupo for c in agrupados}) == 1
    assert r.diferencia == 0
