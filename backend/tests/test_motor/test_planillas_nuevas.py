"""Planillas reales de Lago Ranco y General Córdova (comunidades de partida en producción).

Solo se comparan conteos, períodos y que los totales coincidan con las filas de cierre: nada de
nombres, RUTs ni glosas del cliente.
"""

from __future__ import annotations

import pytest

from motor.dominio import Periodo, TipoPartida
from motor.parsers.libros import leer_libro
from motor.texto import normalizar

pytestmark = pytest.mark.datos_reales

HASTA = Periodo(2026, 9)  # último mes cerrado en los archivos de octubre 2026


def _periodos(libro, desde: Periodo) -> list[Periodo]:
    clave = lambda p: (p.anio, p.mes)  # noqa: E731
    return [p for p in sorted(libro.bloques, key=clave) if clave(desde) <= clave(p) <= clave(HASTA)]


def _rango(desde: Periodo) -> list[Periodo]:
    periodos, p = [], desde
    while (p.anio, p.mes) <= (HASTA.anio, HASTA.mes):
        periodos.append(p)
        p = p.siguiente()
    return periodos


def _sin_descuadre_de_cierre(libro, periodos: list[Periodo]) -> None:
    """La suma de las partidas de cada período es lo que informa su fila de cierre."""
    for periodo in periodos:
        assert periodo in libro.periodos_cerrados
        assert not [a for a in libro.advertencias_de(periodo) if "informa" in a], periodo


def test_ingresos_general_cordova_comp_y_monto_en_haber(datos_general_cordova):
    libro = leer_libro(
        datos_general_cordova / "listado ingresos GENERAL CORDOVA.xlsx", TipoPartida.INGRESO
    )

    periodos = _periodos(libro, Periodo(2025, 11))
    assert periodos == _rango(Periodo(2025, 11))
    assert sum(len(libro.partidas(p)) for p in periodos) == 68
    assert all(p.monto > 0 for per in periodos for p in libro.partidas(per))
    _sin_descuadre_de_cierre(libro, periodos)
    assert libro.advertencias == []


def test_egresos_general_cordova(datos_general_cordova):
    libro = leer_libro(
        datos_general_cordova / "emitir egresos GENERAL CORDOVA.xlsm", TipoPartida.EGRESO
    )

    periodos = _periodos(libro, Periodo(2025, 9))
    assert periodos == _rango(Periodo(2025, 9))
    assert sum(len(libro.partidas(p)) for p in periodos) == 133
    _sin_descuadre_de_cierre(libro, periodos)
    assert libro.advertencias == []


def test_egresos_lago_ranco_glosa_con_cierre_no_corta_bloques(datos_lago_ranco):
    libro = leer_libro(datos_lago_ranco / "emitir egresos BCI LAGO RANCO.xlsm", TipoPartida.EGRESO)

    todas = [p for partidas in libro.bloques.values() for p in partidas]
    con_cierre = [p for p in todas if "CIERRE" in normalizar(p.glosa)]
    assert len(con_cierre) == 6  # antes estas filas se tomaban como cierres de mes
    # El único cierre ilegible es un error de tipeo del cliente en febrero 2023.
    assert sum("no se pudo leer el mes del cierre" in a for a in libro.advertencias) == 1
    recientes = _periodos(libro, Periodo(2025, 3))
    assert recientes == _rango(Periodo(2025, 3))
    _sin_descuadre_de_cierre(libro, [p for p in recientes if p != Periodo(2025, 7)])
    assert sum(len(libro.partidas(p)) for p in recientes) == 522


def test_ingresos_lago_ranco(datos_lago_ranco):
    libro = leer_libro(datos_lago_ranco / "listado ingresos LAGO RANCO.xlsx", TipoPartida.INGRESO)

    recientes = _periodos(libro, Periodo(2026, 4))
    assert recientes == _rango(Periodo(2026, 4))
    _sin_descuadre_de_cierre(libro, recientes)
    assert sum(len(libro.partidas(p)) for p in recientes) == 163
