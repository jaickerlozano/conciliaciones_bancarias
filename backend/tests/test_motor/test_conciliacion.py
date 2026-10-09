from datetime import date

from motor.conciliacion import conciliar
from motor.dominio import (
    Cartola,
    EstadoApertura,
    MovimientoBancario,
    Origen,
    PartidaLibro,
    Periodo,
    TipoPartida,
)


def _cartola(saldo_inicial, movimientos, hasta=date(2026, 5, 29)):
    neto = sum(m.monto_con_signo for m in movimientos)
    return Cartola(
        "Santander", "1", "306", date(2026, 4, 30), hasta,
        saldo_inicial, saldo_inicial + neto, movimientos,
    )  # fmt: skip


def test_pendientes_del_mes_anterior_se_liquidan_y_cuadra():
    cheque_abril = PartidaLibro(
        TipoPartida.EGRESO, 1418, date(2026, 4, 23), 80_000, cheque="1587144"
    )
    deposito_abril = PartidaLibro(TipoPartida.INGRESO, 1188, date(2026, 5, 3), 403_161)
    no_contab_enero = MovimientoBancario(date(2026, 1, 6), "Transf.", 300_000, es_cargo=False)
    apertura = EstadoApertura(
        saldo_registro=1_000_000,
        saldo_banco=1_000_000 + 80_000 - 403_161 + 300_000,
        cheques_pendientes=[cheque_abril],
        depositos_pendientes=[deposito_abril],
        movimientos_no_contabilizados=[no_contab_enero],
    )
    ingresos_mayo = [
        PartidaLibro(TipoPartida.INGRESO, 1210, date(2026, 1, 6), 300_000),  # liquida enero
        PartidaLibro(TipoPartida.INGRESO, 1217, date(2026, 6, 8), 350_000),  # aún no llega
    ]
    egresos_mayo = [
        PartidaLibro(TipoPartida.EGRESO, 1421, date(2026, 5, 26), 728_835, cheque="1587147"),
    ]
    cartola = _cartola(
        apertura.saldo_banco,
        [
            MovimientoBancario(date(2026, 5, 4), "Transf.", 403_161, es_cargo=False),
            MovimientoBancario(date(2026, 5, 6), "Cheque", 80_000, True, documento="1587144"),
            MovimientoBancario(date(2026, 5, 6), "PAC Seguro", 4_414, es_cargo=True),
        ],
    )

    r = conciliar(Periodo(2026, 5), apertura, ingresos_mayo, egresos_mayo, cartola)

    assert r.saldo_registro == 1_000_000 + 650_000 - 728_835
    assert [p.comprobante for p in r.cheques_pendientes] == [1421]
    assert [p.comprobante for p in r.depositos_pendientes] == [1217]
    assert [m.monto_con_signo for m in r.movimientos_no_contabilizados] == [-4_414]
    assert r.cuadra, r.diferencia
    assert r.advertencias == []

    siguiente = r.estado_cierre()
    assert siguiente.saldo_registro == r.saldo_registro
    assert siguiente.saldo_banco == cartola.saldo_final


def test_advierte_cartola_de_otro_mes_y_saldo_discontinuo():
    apertura = EstadoApertura(saldo_registro=0, saldo_banco=999)
    cartola = _cartola(1_000, [], hasta=date(2026, 6, 30))
    r = conciliar(Periodo(2026, 5), apertura, [], [], cartola)
    assert len(r.advertencias) == 2


def test_descarta_movimientos_repetidos_de_cartolas_traslapadas():
    repetido_abono = MovimientoBancario(date(2026, 2, 2), "Transf. X", 351_821, es_cargo=False)
    repetido_cargo = MovimientoBancario(date(2026, 2, 2), "Cheque", 66_010, True, "1587059")
    nuevo = MovimientoBancario(date(2026, 2, 10), "Transf. Y", 100_000, es_cargo=False)
    saldo_fin_enero = 1_000_000
    apertura = EstadoApertura(
        saldo_registro=saldo_fin_enero,
        saldo_banco=saldo_fin_enero,
        movimientos_cartola_anterior=[repetido_abono, repetido_cargo],
    )
    # la cartola de febrero parte antes de que se registraran los movimientos del 02/02
    cartola = Cartola(
        "Santander", "1", "303", date(2026, 1, 30), date(2026, 2, 27),
        saldo_fin_enero - 351_821 + 66_010, saldo_fin_enero + 100_000,
        [repetido_abono, repetido_cargo, nuevo],
    )  # fmt: skip
    ingreso = PartidaLibro(TipoPartida.INGRESO, 1, date(2026, 2, 10), 100_000)

    r = conciliar(Periodo(2026, 2), apertura, [ingreso], [], cartola)

    assert r.movimientos_descartados == [repetido_abono, repetido_cargo]
    assert r.movimientos_no_contabilizados == []
    assert r.cuadra
    assert len(r.advertencias) == 1 and "traslapa" in r.advertencias[0]
    assert r.estado_cierre().movimientos_cartola_anterior == cartola.movimientos


def test_repetido_con_fecha_y_descripcion_distintas_entre_formatos():
    """La consulta de enero fecha un abono el 31/01; la cartola oficial de febrero, el 02/02."""
    from motor.conciliacion import descartar_repetidos

    enero = [
        MovimientoBancario(date(2026, 1, 31), "Transf. Fondos desde", 351_821, False),
        MovimientoBancario(date(2026, 2, 2), "Cheque Canje", 66_010, True, "001587059"),
    ]
    febrero = [
        MovimientoBancario(date(2026, 2, 2), "0106472769 Transf. Rodrigo", 351_821, False),
        MovimientoBancario(date(2026, 2, 2), "Cheque Canje Recibido", 66_010, True, "1587059"),
        MovimientoBancario(date(2026, 2, 2), "Cheque Canje Recibido", 66_010, True, "1587060"),
    ]
    nuevos, repetidos = descartar_repetidos(febrero, enero)
    assert repetidos == febrero[:2]
    assert nuevos == [febrero[2]]  # mismo monto pero otro cheque


def test_no_busca_repetidos_si_la_cartola_continua():
    pago = MovimientoBancario(date(2026, 3, 2), "Transf. depto 41", 272_473, False)
    apertura = EstadoApertura(
        saldo_registro=1_000_000, saldo_banco=1_000_000,
        movimientos_cartola_anterior=[
            MovimientoBancario(date(2026, 2, 27), "Transf. depto 42", 272_473, False)
        ],
    )  # fmt: skip
    cartola = _cartola(1_000_000, [pago], hasta=date(2026, 3, 31))
    r = conciliar(Periodo(2026, 3), apertura, [], [], cartola)
    assert r.movimientos_descartados == []
    assert r.movimientos_no_contabilizados == [pago]


def _cheque_cobrado_por(monto_banco):
    """Cheque 179840 registrado por $654.852 y cobrado por `monto_banco`."""
    apertura = EstadoApertura(saldo_registro=1_000_000, saldo_banco=1_000_000)
    egreso = PartidaLibro(
        TipoPartida.EGRESO, 5310, date(2026, 6, 2), 654_852, glosa="Sueldo", cheque="179840"
    )
    cobro = MovimientoBancario(date(2026, 6, 5), "Cheque", monto_banco, True, documento="179840")
    cartola = _cartola(1_000_000, [cobro], hasta=date(2026, 6, 30))
    r = conciliar(Periodo(2026, 6), apertura, [], [egreso], cartola)
    return r, cobro


def test_cheque_cobrado_por_menos_deja_la_diferencia_como_cheque_pendiente():
    r, cobro = _cheque_cobrado_por(645_852)

    assert r.saldo_registro == 1_000_000 - 654_852  # el libro registra el egreso completo
    assert len(r.cheques_pendientes) == 1
    dif = r.cheques_pendientes[0]
    assert (dif.tipo, dif.monto, dif.comprobante, dif.cheque) == (
        TipoPartida.EGRESO,
        9_000,
        5310,
        "179840",
    )
    assert dif.origen == Origen.DIFERENCIA
    assert dif.fecha == cobro.fecha
    assert "179840" in dif.glosa and "$654.852" in dif.glosa and "$645.852" in dif.glosa
    assert r.movimientos_no_contabilizados == []
    assert r.cuadra, r.diferencia
    # el cruce sigue marcado para revisión
    assert len(r.cruces) == 1 and r.cruces[0].requiere_revision


def test_cheque_cobrado_por_mas_deja_la_diferencia_como_cargo_no_contabilizado():
    r, cobro = _cheque_cobrado_por(660_852)

    assert r.cheques_pendientes == []
    assert len(r.movimientos_no_contabilizados) == 1
    dif = r.movimientos_no_contabilizados[0]
    assert (dif.monto, dif.es_cargo, dif.documento) == (6_000, True, "179840")
    assert dif.origen == Origen.DIFERENCIA
    assert dif.fecha == cobro.fecha
    assert "179840" in dif.descripcion and "$6.000" in dif.descripcion
    assert r.movimientos_cartola == [cobro]  # la diferencia no es un movimiento de la cartola
    assert r.cuadra, r.diferencia


def test_cheque_con_monto_igual_no_genera_diferencia():
    r, _ = _cheque_cobrado_por(654_852)
    assert r.cheques_pendientes == [] and r.movimientos_no_contabilizados == []
    assert r.cuadra


def test_diferencia_de_redondeo_en_cheque_no_se_separa():
    """Hasta $100 es decimal de UF: se absorbe con el ajuste por redondeo (Cinema, enero 2026)."""
    r, _ = _cheque_cobrado_por(654_852 - 100)
    assert r.cheques_pendientes == [] and r.movimientos_no_contabilizados == []
    assert r.diferencia == 100  # el usuario la ajusta con el redondeo
    assert r.cruces[0].requiere_revision


def test_diferencia_de_cheque_se_arrastra_al_mes_siguiente():
    r, _ = _cheque_cobrado_por(645_852)
    apertura = r.estado_cierre()
    assert [p.monto for p in apertura.cheques_pendientes] == [9_000]

    julio = _cartola(r.saldo_banco, [], hasta=date(2026, 7, 31))
    r2 = conciliar(Periodo(2026, 7), apertura, [], [], julio)

    assert [(p.monto, p.origen) for p in r2.cheques_pendientes] == [(9_000, Origen.DIFERENCIA)]
    assert r2.cuadra, r2.diferencia


def test_diferencia_de_cargo_se_arrastra_y_no_se_descarta_como_repetida():
    r, _ = _cheque_cobrado_por(660_852)
    apertura = r.estado_cierre()
    # cartola de julio que no continúa: activa la búsqueda de repetidos
    julio = _cartola(r.saldo_banco + 1, [], hasta=date(2026, 7, 31))
    r2 = conciliar(Periodo(2026, 7), apertura, [], [], julio)

    assert [(m.monto, m.origen) for m in r2.movimientos_no_contabilizados] == [
        (6_000, Origen.DIFERENCIA)
    ]
