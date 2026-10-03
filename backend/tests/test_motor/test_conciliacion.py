from datetime import date

from motor.conciliacion import conciliar
from motor.dominio import (
    Cartola,
    EstadoApertura,
    MovimientoBancario,
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
