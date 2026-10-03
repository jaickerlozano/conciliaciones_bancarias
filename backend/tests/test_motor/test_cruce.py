from datetime import date

from motor.cruce import ConfigCruce, cruzar
from motor.dominio import MovimientoBancario, PartidaLibro, TipoCruce, TipoPartida


def egreso(comp, monto, cheque="", fecha=date(2026, 5, 26)):
    return PartidaLibro(TipoPartida.EGRESO, comp, fecha, monto, cheque=cheque)


def ingreso(comp, monto, fecha):
    return PartidaLibro(TipoPartida.INGRESO, comp, fecha, monto)


def cargo(monto, doc="", fecha=date(2026, 5, 28), desc="Cheque Pagado"):
    return MovimientoBancario(fecha, desc, monto, es_cargo=True, documento=doc)


def abono(monto, fecha, desc="Transf."):
    return MovimientoBancario(fecha, desc, monto, es_cargo=False)


def test_cheque_cruza_por_numero_aunque_haya_otro_cargo_del_mismo_monto():
    e = egreso(1, 50_000, cheque="1587130")
    c_otro = cargo(50_000, doc="9999999")
    c_cheque = cargo(50_000, doc="1587130")
    r = cruzar([e], [], [c_otro, c_cheque])
    assert len(r.cruces) == 1
    assert r.cruces[0].movimiento is c_cheque
    assert r.cruces[0].tipo == TipoCruce.CHEQUE
    assert r.movimientos_sin_cruce == [c_otro]


def test_cheque_con_monto_distinto_se_cruza_con_nota():
    r = cruzar([egreso(1, 125_661, cheque="1587090")], [], [cargo(125_660, doc="1587090")])
    assert r.cruces[0].requiere_revision
    assert "Monto distinto" in r.cruces[0].nota


def test_cheque_no_cobrado_queda_pendiente():
    e = egreso(1, 80_000, cheque="1587144")
    r = cruzar([e], [], [cargo(80_000, doc="1587145")])
    # el cargo no es ese cheque, pero sí coincide por monto en la capa 2: se sugiere, no se fuerza
    assert r.cruces[0].tipo != TipoCruce.CHEQUE


def test_egreso_sin_cheque_cruza_por_monto():
    e = egreso(1443, 4_414, cheque="PAC", fecha=date(2026, 5, 26))
    c = cargo(4_414, doc="5048045", fecha=date(2026, 5, 6), desc="PAC Seg. Fraude")
    r = cruzar([e], [], [c])
    assert r.cruces[0].movimiento is c
    assert r.cruces[0].tipo == TipoCruce.SUGERIDO  # 20 días de diferencia


def test_ingresos_iguales_se_asignan_por_cercania_y_sobra_el_mas_lejano():
    partidas = [
        ingreso(1211, 272_473, date(2026, 5, 14)),
        ingreso(1200, 272_473, date(2026, 5, 15)),
        ingreso(1213, 272_473, date(2026, 5, 19)),
        ingreso(1201, 272_473, date(2026, 5, 20)),
        ingreso(1202, 272_473, date(2026, 5, 31)),
    ]
    movs = [
        abono(272_473, date(2026, 5, 14)),
        abono(272_473, date(2026, 5, 15)),
        abono(272_473, date(2026, 5, 15)),
        abono(272_473, date(2026, 5, 19)),
    ]
    r = cruzar([], partidas, movs)
    assert [p.comprobante for p in r.ingresos_sin_cruce] == [1202]
    assert all(c.tipo == TipoCruce.SUGERIDO for c in r.cruces)  # ambiguo: 5 vs 4


def test_cruce_unico_y_cercano_es_automatico():
    r = cruzar([], [ingreso(1, 494_931, date(2026, 5, 20))], [abono(494_931, date(2026, 5, 20))])
    assert r.cruces[0].tipo == TipoCruce.MONTO_FECHA
    assert not r.cruces[0].requiere_revision


def test_fuera_de_ventana_no_cruza():
    r = cruzar(
        [],
        [ingreso(1, 100_000, date(2026, 1, 1))],
        [abono(100_000, date(2026, 5, 1))],
        ConfigCruce(ventana_dias=60),
    )
    assert r.cruces == []
    assert len(r.ingresos_sin_cruce) == 1
    assert len(r.movimientos_sin_cruce) == 1


def test_ingreso_no_cruza_con_cargo():
    r = cruzar([], [ingreso(1, 50_000, date(2026, 5, 5))], [cargo(50_000, fecha=date(2026, 5, 5))])
    assert r.cruces == []


def test_cheque_truncado_en_la_cartola_cruza_si_el_monto_es_igual():
    e = egreso(1, 1_379_448, cheque="1587109")
    distinto = cargo(1_379_000, doc="87109")
    igual = cargo(1_379_448, doc="87109")
    r = cruzar([e], [], [distinto, igual])
    assert r.cruces[0].movimiento is igual
    assert r.cruces[0].tipo == TipoCruce.CHEQUE


def test_terminacion_corta_no_cruza_por_cheque():
    r = cruzar([egreso(1, 10_000, cheque="1587109")], [], [cargo(10_000, doc="109")])
    assert r.cruces[0].tipo != TipoCruce.CHEQUE
