"""Cruce entre partidas del libro y movimientos de la cartola.

Capas, de más a menos segura:
1. Egresos con nº de cheque  <->  cargos cuyo nº de documento es ese cheque.
2. Egresos restantes (PAC, transferencias)  <->  cargos restantes, por monto y fecha.
3. Ingresos  <->  abonos, por monto y fecha.

En las capas 2 y 3, dentro de cada grupo de igual monto se busca la asignación que maximiza
la cantidad de cruces y, a igualdad, minimiza la suma de días de diferencia (programación
dinámica sobre ambas listas ordenadas por fecha; en 1D la asignación óptima no se cruza).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from motor.dominio import Cruce, MovimientoBancario, PartidaLibro, TipoCruce
from motor.texto import fmt_clp

DIAS_SIN_FECHA = 10_000  # costo para partidas sin fecha: se cruzan solo si no hay otra opción


@dataclass(frozen=True)
class ConfigCruce:
    ventana_dias: int = 60  # diferencia máxima de días para proponer un cruce por monto
    dias_seguro: int = 7  # hasta esta diferencia un cruce por monto no ambiguo es automático


@dataclass
class ResultadoCruce:
    cruces: list[Cruce] = field(default_factory=list)
    egresos_sin_cruce: list[PartidaLibro] = field(default_factory=list)
    ingresos_sin_cruce: list[PartidaLibro] = field(default_factory=list)
    movimientos_sin_cruce: list[MovimientoBancario] = field(default_factory=list)


def cruzar(
    egresos: list[PartidaLibro],
    ingresos: list[PartidaLibro],
    movimientos: list[MovimientoBancario],
    config: ConfigCruce | None = None,
) -> ResultadoCruce:
    config = config or ConfigCruce()
    cargos = [m for m in movimientos if m.es_cargo]
    abonos = [m for m in movimientos if not m.es_cargo]

    cruces_cheque, egresos_rest, cargos_rest = _cruzar_cheques(egresos, cargos)
    cruces_eg, egresos_rest, cargos_rest = _cruzar_por_monto(egresos_rest, cargos_rest, config)
    cruces_in, ingresos_rest, abonos_rest = _cruzar_por_monto(ingresos, abonos, config)

    usados = {id(m) for m in cargos_rest + abonos_rest}
    return ResultadoCruce(
        cruces=cruces_cheque + cruces_eg + cruces_in,
        egresos_sin_cruce=egresos_rest,
        ingresos_sin_cruce=ingresos_rest,
        # se conserva el orden original de la cartola
        movimientos_sin_cruce=[m for m in movimientos if id(m) in usados],
    )


def _normalizar_doc(doc: str) -> str:
    return doc.strip().lstrip("0")


def _cruzar_cheques(
    egresos: list[PartidaLibro], cargos: list[MovimientoBancario]
) -> tuple[list[Cruce], list[PartidaLibro], list[MovimientoBancario]]:
    por_doc: dict[str, list[MovimientoBancario]] = defaultdict(list)
    for c in cargos:
        if c.documento:
            por_doc[_normalizar_doc(c.documento)].append(c)

    cruces: list[Cruce] = []
    sin_cruce: list[PartidaLibro] = []
    usados: set[int] = set()
    for e in egresos:
        numero = e.numero_cheque
        candidatos = (
            [c for c in por_doc.get(_normalizar_doc(numero), []) if id(c) not in usados]
            if numero
            else []
        )
        if not candidatos:
            sin_cruce.append(e)
            continue
        # si hubiera varios cargos con el mismo nº, preferir el de monto idéntico
        cargo = min(candidatos, key=lambda c: abs(c.monto - e.monto))
        usados.add(id(cargo))
        nota = ""
        if cargo.monto != e.monto:
            nota = f"Monto distinto: libro {fmt_clp(e.monto)} vs banco {fmt_clp(cargo.monto)}."
        cruces.append(Cruce(e, cargo, TipoCruce.CHEQUE, nota))
    return cruces, sin_cruce, [c for c in cargos if id(c) not in usados]


def _dias(a: date | None, b: date) -> int:
    return DIAS_SIN_FECHA if a is None else abs((a - b).days)


def _cruzar_por_monto(
    partidas: list[PartidaLibro], movimientos: list[MovimientoBancario], config: ConfigCruce
) -> tuple[list[Cruce], list[PartidaLibro], list[MovimientoBancario]]:
    partidas_por_monto: dict[int, list[PartidaLibro]] = defaultdict(list)
    movs_por_monto: dict[int, list[MovimientoBancario]] = defaultdict(list)
    for p in partidas:
        partidas_por_monto[p.monto].append(p)
    for m in movimientos:
        movs_por_monto[m.monto].append(m)

    cruces: list[Cruce] = []
    for monto, grupo_p in partidas_por_monto.items():
        grupo_m = movs_por_monto.get(monto)
        if not grupo_m:
            continue
        grupo_p.sort(key=lambda p: p.fecha or date.max)
        grupo_m.sort(key=lambda m: m.fecha)
        pares = _asignacion_optima(grupo_p, grupo_m, config.ventana_dias)
        # Si sobran partidas o movimientos de este monto, cuál queda pendiente es una decisión.
        ambiguo = len(grupo_p) != len(grupo_m)
        for i, j in pares:
            p, m = grupo_p[i], grupo_m[j]
            dias = _dias(p.fecha, m.fecha)
            if ambiguo:
                tipo, nota = (
                    TipoCruce.SUGERIDO,
                    (
                        f"Hay {len(grupo_p)} partidas y {len(grupo_m)} movimientos de "
                        f"{fmt_clp(monto)}: confirmar cuál corresponde."
                    ),
                )
            elif dias > config.dias_seguro:
                tipo, nota = TipoCruce.SUGERIDO, f"Fechas separadas por {dias} días."
            else:
                tipo, nota = TipoCruce.MONTO_FECHA, ""
            cruces.append(Cruce(p, m, tipo, nota))

    usados_p = {id(c.partida) for c in cruces}
    usados_m = {id(c.movimiento) for c in cruces}
    return (
        cruces,
        [p for p in partidas if id(p) not in usados_p],
        [m for m in movimientos if id(m) not in usados_m],
    )


def _asignacion_optima(
    partidas: list[PartidaLibro], movimientos: list[MovimientoBancario], ventana: int
) -> list[tuple[int, int]]:
    """Máximo nº de pares (|días| <= ventana) con mínima suma de días. Listas ya ordenadas."""
    n, m = len(partidas), len(movimientos)
    # mejor[i][j] = (cantidad de pares, -suma de días) usando partidas[:i] y movimientos[:j]
    mejor = [[(0, 0)] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            opciones = [mejor[i - 1][j], mejor[i][j - 1]]
            d = _dias(partidas[i - 1].fecha, movimientos[j - 1].fecha)
            if d <= ventana or partidas[i - 1].fecha is None:
                cant, costo = mejor[i - 1][j - 1]
                opciones.append((cant + 1, costo - d))
            mejor[i][j] = max(opciones)

    pares: list[tuple[int, int]] = []
    i, j = n, m
    while i > 0 and j > 0:
        if mejor[i][j] == mejor[i - 1][j]:
            i -= 1
        elif mejor[i][j] == mejor[i][j - 1]:
            j -= 1
        else:
            pares.append((i - 1, j - 1))
            i, j = i - 1, j - 1
    return list(reversed(pares))
