"""Cálculo de la conciliación bancaria de un período.

    Saldo según registro    = saldo registro mes anterior + ingresos del mes − egresos del mes
    Saldo según conciliación = registro + cheques girados no cobrados
                               − depósitos contabilizados no registrados en banco
                               + movimientos del banco no contabilizados (abonos +, cargos −)
    Diferencia              = saldo según banco − saldo según conciliación   (debe ser 0)

Los pendientes del mes anterior (EstadoApertura) vuelven a cruzarse contra la cartola nueva:
un cheque girado en abril y cobrado en mayo sale solo de la lista.

Si un cheque se cruza por número pero el banco lo cobró por otro monto, la diferencia queda
pendiente (origen `diferencia`): si cobró menos, como cheque girado no cobrado por la
diferencia; si cobró más, como cargo no contabilizado. Así la conciliación cuadra y la
diferencia sigue a la vista, mes a mes, hasta que se aclare. Las diferencias de hasta $100
(decimales de cuotas en UF) no se separan: se absorben con el ajuste por redondeo, como hace
el cliente.

Si la cartola se traslapa con la anterior (ej. la de febrero empieza el 30/01 y repite
movimientos ya conciliados en enero), los movimientos repetidos se descartan.
"""

from __future__ import annotations

from dataclasses import replace

from motor.cruce import ConfigCruce, cruzar
from motor.dominio import (
    Cartola,
    Cruce,
    EstadoApertura,
    MovimientoBancario,
    Origen,
    PartidaLibro,
    Periodo,
    ResultadoConciliacion,
    TipoCruce,
    TipoPartida,
)
from motor.texto import fmt_clp

DIAS_TOLERANCIA_REPETIDO = 5
# Hasta este monto una diferencia de cobro de cheque es de redondeo (decimales de UF) y se
# absorbe con el ajuste por redondeo; sobre él queda como pendiente.
MAX_DIFERENCIA_REDONDEO = 100


def conciliar(
    periodo: Periodo,
    apertura: EstadoApertura,
    ingresos: list[PartidaLibro],
    egresos: list[PartidaLibro],
    cartola: Cartola,
    redondeo: int = 0,
    config: ConfigCruce | None = None,
) -> ResultadoConciliacion:
    # Solo se buscan repetidos si la cartola no continúa limpiamente desde el saldo anterior:
    # así un pago legítimo del mismo monto que uno del mes pasado nunca se descarta.
    continua = apertura.saldo_banco is not None and apertura.saldo_banco == cartola.saldo_inicial
    if continua:
        nuevos, descartados = list(cartola.movimientos), []
    else:
        nuevos, descartados = descartar_repetidos(
            cartola.movimientos, apertura.movimientos_cartola_anterior
        )
    advertencias = _validar_entradas(periodo, apertura, cartola, descartados)

    egresos_candidatos = _con_origen(apertura.cheques_pendientes) + egresos
    ingresos_candidatos = _con_origen(apertura.depositos_pendientes) + ingresos
    movimientos: list[MovimientoBancario] = [
        replace(m, origen=_origen_arrastrado(m.origen))
        for m in apertura.movimientos_no_contabilizados
    ] + nuevos

    resultado_cruce = cruzar(egresos_candidatos, ingresos_candidatos, movimientos, config)
    cheques_dif, cargos_dif = diferencias_de_cheques(resultado_cruce.cruces)

    return ResultadoConciliacion(
        periodo=periodo,
        saldo_anterior=apertura.saldo_registro,
        total_ingresos=sum(p.monto for p in ingresos),
        total_egresos=sum(p.monto for p in egresos),
        redondeo=redondeo,
        cheques_pendientes=resultado_cruce.egresos_sin_cruce + cheques_dif,
        depositos_pendientes=resultado_cruce.ingresos_sin_cruce,
        movimientos_no_contabilizados=resultado_cruce.movimientos_sin_cruce + cargos_dif,
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

    Cada movimiento anterior puede descartar a lo más un movimiento nuevo.
    """
    disponibles = list(anteriores)
    nuevos: list[MovimientoBancario] = []
    repetidos: list[MovimientoBancario] = []
    for m in movimientos:
        candidatos = [a for a in disponibles if _mismo_movimiento(a, m)]
        if candidatos:
            previo = min(candidatos, key=lambda a: abs((a.fecha - m.fecha).days))
            disponibles.remove(previo)
            repetidos.append(m)
        else:
            nuevos.append(m)
    return nuevos, repetidos


def _mismo_movimiento(a: MovimientoBancario, b: MovimientoBancario) -> bool:
    """Mismo movimiento visto en dos cartolas. Los formatos difieren en descripción y a veces en
    la fecha (operación vs. contable), por eso se compara monto, sentido, nº de documento (si
    ambos lo traen) y una tolerancia de días."""
    if a.monto != b.monto or a.es_cargo != b.es_cargo:
        return False
    if abs((a.fecha - b.fecha).days) > DIAS_TOLERANCIA_REPETIDO:
        return False
    doc_a, doc_b = a.documento.strip().lstrip("0"), b.documento.strip().lstrip("0")
    return not (doc_a and doc_b) or doc_a == doc_b


def diferencias_de_cheques(
    cruces: list[Cruce],
) -> tuple[list[PartidaLibro], list[MovimientoBancario]]:
    """Pendientes que explican los cheques cobrados por un monto distinto al registrado.

    Devuelve (egresos pendientes, cargos no contabilizados), ambos con origen `diferencia`.
    """
    egresos: list[PartidaLibro] = []
    cargos: list[MovimientoBancario] = []
    for cruce in cruces:
        partida, mov = cruce.partida, cruce.movimiento
        dif = partida.monto - mov.monto
        if cruce.tipo != TipoCruce.CHEQUE or abs(dif) <= MAX_DIFERENCIA_REDONDEO:
            continue
        numero = partida.cheque or mov.documento
        if dif > 0:  # el banco cobró menos: falta que cobre la diferencia
            egresos.append(
                PartidaLibro(
                    tipo=TipoPartida.EGRESO,
                    comprobante=partida.comprobante,
                    fecha=mov.fecha,
                    monto=dif,
                    glosa=(
                        f"Diferencia en el cobro del cheque {numero}: libro "
                        f"{fmt_clp(partida.monto)}, banco {fmt_clp(mov.monto)}"
                    ),
                    depto=partida.depto,
                    cheque=partida.cheque,
                    origen=Origen.DIFERENCIA,
                )
            )
        else:  # el banco cobró más de lo registrado
            cargos.append(
                MovimientoBancario(
                    fecha=mov.fecha,
                    descripcion=(
                        f"Diferencia en el cobro del cheque {numero}: banco cobró "
                        f"{fmt_clp(-dif)} más que lo registrado"
                    ),
                    monto=-dif,
                    es_cargo=True,
                    documento=mov.documento,
                    sucursal=mov.sucursal,
                    origen=Origen.DIFERENCIA,
                )
            )
    return egresos, cargos


def _origen_arrastrado(origen: Origen) -> Origen:
    """Lo pendiente pasa como arrastre, salvo las diferencias de cheque, que conservan su origen
    para que el usuario las siga reconociendo."""
    return origen if origen == Origen.DIFERENCIA else Origen.ARRASTRE


def _con_origen(partidas: list[PartidaLibro]) -> list[PartidaLibro]:
    return [replace(p, origen=_origen_arrastrado(p.origen)) for p in partidas]


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
