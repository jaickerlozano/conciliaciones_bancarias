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


# --- cruce agrupado: varias partidas <-> un movimiento


def test_deposito_agrupado_de_dos_ingresos():
    a = ingreso(34917, 168_465, date(2026, 5, 29))
    b = ingreso(34918, 117_331, date(2026, 5, 30))
    otro = ingreso(1, 50_000, date(2026, 5, 30))
    deposito = abono(285_796, date(2026, 6, 3))
    r = cruzar([], [a, otro, b], [deposito])
    assert len(r.cruces) == 2
    assert {c.partida.comprobante for c in r.cruces} == {34917, 34918}
    assert all(c.movimiento is deposito for c in r.cruces)
    assert all(c.tipo == TipoCruce.AGRUPADO and c.requiere_revision for c in r.cruces)
    assert r.cruces[0].grupo and r.cruces[0].grupo == r.cruces[1].grupo
    assert "2 partidas suman $285.796" in r.cruces[0].nota
    assert r.movimientos_sin_cruce == []
    assert r.ingresos_sin_cruce == [otro]


def test_agrupado_respeta_la_ventana_de_dias():
    a = ingreso(1, 100_000, date(2026, 5, 1))  # 33 días antes del depósito
    b = ingreso(2, 50_000, date(2026, 6, 2))
    deposito = abono(150_000, date(2026, 6, 3))
    r = cruzar([], [a, b], [deposito])
    assert r.cruces == []
    assert r.movimientos_sin_cruce == [deposito]


def test_agrupado_no_aplica_si_hay_cruce_uno_a_uno():
    exacto = ingreso(1, 100_000, date(2026, 6, 3))
    a = ingreso(2, 60_000, date(2026, 6, 2))
    b = ingreso(3, 40_000, date(2026, 6, 2))
    deposito = abono(100_000, date(2026, 6, 3))
    r = cruzar([], [a, b, exacto], [deposito])
    assert len(r.cruces) == 1
    assert r.cruces[0].partida is exacto
    assert r.cruces[0].tipo == TipoCruce.MONTO_FECHA
    assert r.ingresos_sin_cruce == [a, b]


def test_cargo_agrupado_de_tres_egresos_sin_cheque():
    e1 = egreso(1, 10_000, cheque="PAC", fecha=date(2026, 6, 1))
    e2 = egreso(2, 20_000, cheque="PAC", fecha=date(2026, 6, 2))
    e3 = egreso(3, 30_000, cheque="TRANSF", fecha=date(2026, 6, 3))
    c = cargo(60_000, fecha=date(2026, 6, 5), desc="Pago masivo")
    r = cruzar([e1, e2, e3], [], [c])
    assert sorted(x.partida.comprobante for x in r.cruces) == [1, 2, 3]
    assert len({x.grupo for x in r.cruces}) == 1
    assert all(x.tipo == TipoCruce.AGRUPADO for x in r.cruces)
    assert r.egresos_sin_cruce == [] and r.movimientos_sin_cruce == []


def test_agrupado_prefiere_la_combinacion_mas_cercana_y_avisa_si_empata():
    lejos_a = ingreso(1, 70_000, date(2026, 5, 22))
    lejos_b = ingreso(2, 30_000, date(2026, 5, 22))
    cerca_a = ingreso(3, 60_000, date(2026, 6, 1))
    cerca_b = ingreso(4, 40_000, date(2026, 6, 1))
    deposito = abono(100_000, date(2026, 6, 2))
    r = cruzar([], [lejos_a, lejos_b, cerca_a, cerca_b], [deposito])
    assert {c.partida.comprobante for c in r.cruces} == {3, 4}

    empate_a = ingreso(5, 55_000, date(2026, 6, 1))
    empate_b = ingreso(6, 45_000, date(2026, 6, 1))
    r = cruzar([], [cerca_a, cerca_b, empate_a, empate_b], [abono(100_000, date(2026, 6, 2))])
    assert len(r.cruces) == 2
    assert "otra combinación" in r.cruces[0].nota
