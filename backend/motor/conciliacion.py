"""Cálculo de la conciliación bancaria de un período.

    Saldo según registro    = saldo registro mes anterior + ingresos del mes − egresos del mes
    Saldo según conciliación = registro + cheques girados no cobrados
                               − depósitos contabilizados no registrados en banco
                               + movimientos del banco no contabilizados (abonos +, cargos −)
    Diferencia              = saldo según banco − saldo según conciliación   (debe ser 0)

Los pendientes del mes anterior (EstadoApertura) vuelven a cruzarse contra la cartola nueva:
un cheque girado en abril y cobrado en mayo sale solo de la lista.

Si la cartola se traslapa con la anterior (ej. la de febrero empieza el 30/01 y repite
movimientos ya conciliados en enero), los movimientos repetidos se descartan.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from motor.cruce import ConfigCruce, cruzar
from motor.dominio import (
    Cartola,
    EstadoApertura,
    MovimientoBancario,
    Origen,
    PartidaLibro,
    Periodo,
    ResultadoConciliacion,
)
from motor.texto import fmt_clp


def conciliar(
    periodo: Periodo,
    apertura: EstadoApertura,
    ingresos: list[PartidaLibro],
    egresos: list[PartidaLibro],
    cartola: Cartola,
    redondeo: int = 0,
    config: ConfigCruce | None = None,
) -> ResultadoConciliacion:
    nuevos, descartados = descartar_repetidos(
        cartola.movimientos, apertura.movimientos_cartola_anterior
    )
    advertencias = _validar_entradas(periodo, apertura, cartola, descartados)

    egresos_candidatos = _con_origen(apertura.cheques_pendientes, Origen.ARRASTRE) + egresos
    ingresos_candidatos = _con_origen(apertura.depositos_pendientes, Origen.ARRASTRE) + ingresos
    movimientos: list[MovimientoBancario] = [
        replace(m, origen=Origen.ARRASTRE) for m in apertura.movimientos_no_contabilizados
    ] + nuevos

    resultado_cruce = cruzar(egresos_candidatos, ingresos_candidatos, movimientos, config)

    return ResultadoConciliacion(
        periodo=periodo,
        saldo_anterior=apertura.saldo_registro,
        total_ingresos=sum(p.monto for p in ingresos),
        total_egresos=sum(p.monto for p in egresos),
        redondeo=redondeo,
        cheques_pendientes=resultado_cruce.egresos_sin_cruce,
        depositos_pendientes=resultado_cruce.ingresos_sin_cruce,
        movimientos_no_contabilizados=resultado_cruce.movimientos_sin_cruce,
        saldo_banco=cartola.saldo_final,
        cruces=resultado_cruce.cruces,
        advertencias=advertencias + cartola.advertencias,
        movimientos_cartola=list(cartola.movimientos),
        movimientos_descartados=descartados,
    )


def descartar_repetidos(
    movimientos: list[MovimientoBancario], anteriores: list[MovimientoBancario]
) -> tuple[list[MovimientoBancario], list[MovimientoBancario]]:
    """Separa los movimientos que ya venían en la cartola anterior. Devuelve (nuevos, repetidos).

    Se compara como multiconjunto: si la cartola anterior traía un movimiento idéntico, se
    descarta uno solo en la nueva.
    """
    disponibles = Counter(m.huella for m in anteriores)
    nuevos: list[MovimientoBancario] = []
    repetidos: list[MovimientoBancario] = []
    for m in movimientos:
        if disponibles[m.huella] > 0:
            disponibles[m.huella] -= 1
            repetidos.append(m)
        else:
            nuevos.append(m)
    return nuevos, repetidos


def _con_origen(partidas: list[PartidaLibro], origen: Origen) -> list[PartidaLibro]:
    return [replace(p, origen=origen) for p in partidas]


def _validar_entradas(
    periodo: Periodo,
    apertura: EstadoApertura,
    cartola: Cartola,
    descartados: list[MovimientoBancario],
) -> list[str]:
    advertencias: list[str] = []
    if descartados:
        advertencias.append(
            f"La cartola se traslapa con la anterior: se descartaron {len(descartados)} "
            "movimientos que ya estaban conciliados el mes pasado."
        )
    if (cartola.hasta.year, cartola.hasta.month) != (periodo.anio, periodo.mes):
        advertencias.append(
            f"La cartola termina el {cartola.hasta:%d/%m/%Y}, que no corresponde al "
            f"período {periodo}."
        )
    # el saldo inicial "efectivo" excluye los movimientos repetidos de la cartola anterior
    saldo_inicial = cartola.saldo_inicial + sum(m.monto_con_signo for m in descartados)
    if apertura.saldo_banco is not None and apertura.saldo_banco != saldo_inicial:
        advertencias.append(
            f"El saldo inicial de la cartola ({fmt_clp(cartola.saldo_inicial)}) no coincide "
            f"con el saldo final del mes anterior ({fmt_clp(apertura.saldo_banco)}). "
            "¿Falta una cartola o se traslapa con la anterior?"
        )
    return advertencias
