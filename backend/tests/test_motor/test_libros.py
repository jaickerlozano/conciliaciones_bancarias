"""Planillas de ingresos/egresos construidas en código (sin datos del cliente)."""

from datetime import datetime

import openpyxl

from motor.dominio import Periodo, TipoPartida
from motor.parsers.libros import leer_libro

ENCABEZADO_CON_TORRE = (
    "FECHA", "CONCEPTO", "COMPROBANTE", "TORRE", "DEPTO", "DETALLE", "DEBE", "HABER", "SALDO",
)  # fmt: skip


def _planilla(tmp_path, encabezado, filas):
    wb = openpyxl.Workbook()
    hoja = wb.active
    hoja.title = "ACUMULADO"
    hoja.append(encabezado)
    for fila in filas:
        hoja.append(fila)
    ruta = tmp_path / "ingresos.xlsx"
    wb.save(ruta)
    return ruta


def test_torre_se_antepone_al_depto(tmp_path):
    ruta = _planilla(
        tmp_path,
        ENCABEZADO_CON_TORRE,
        [
            (datetime(2026, 5, 4), "INGRESO", 1, 61.0, 703.0, "Gasto común", 100_000, None, None),
            (datetime(2026, 5, 5), "INGRESO", 2, 45, "703", "Gasto común", 90_000, None, None),
            (datetime(2026, 5, 6), "INGRESO", 3, None, 101, "Sin torre", 50_000, None, None),
            (None, "CIERRE MES MAYO 2026", None, None, None, None, None, None, None),
        ],
    )

    libro = leer_libro(ruta, TipoPartida.INGRESO)

    deptos = [p.depto for p in libro.partidas(Periodo(2026, 5))]
    assert deptos == ["61-703", "45-703", "101"]


def test_sin_columna_torre_el_depto_no_cambia(tmp_path):
    encabezado = tuple(c for c in ENCABEZADO_CON_TORRE if c != "TORRE")
    ruta = _planilla(
        tmp_path,
        encabezado,
        [
            (datetime(2026, 5, 4), "INGRESO", 1, 703, "Gasto común", 100_000, None, None),
            (None, "CIERRE MES MAYO 2026", None, None, None, None, None, None),
        ],
    )

    libro = leer_libro(ruta, TipoPartida.INGRESO)

    assert [p.depto for p in libro.partidas(Periodo(2026, 5))] == ["703"]
