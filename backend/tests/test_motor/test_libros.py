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


ENCABEZADO_EGRESOS = (
    "FECHA", "CONCEPTO", "COMPROB", "DEPTO", "DETALLE", "numero de cheque", "HABER", "SALDO",
)  # fmt: skip


def _planilla_egresos(tmp_path, filas):
    wb = openpyxl.Workbook()
    hoja = wb.active
    hoja.title = "LISTADO EGRESOS"
    hoja.append(ENCABEZADO_EGRESOS)
    for fila in filas:
        hoja.append(fila)
    ruta = tmp_path / "egresos.xlsx"
    wb.save(ruta)
    return ruta


def test_glosa_con_cierre_no_corta_el_bloque(tmp_path):
    ruta = _planilla_egresos(
        tmp_path,
        [
            (datetime(2026, 5, 4), "EGRESO", 10, None, "Proveedor, CIERRE PORTON", 1, 50_000, None),
            (datetime(2026, 5, 5), "EGRESO", 11, None, "Mantención", 2, 30_000, None),
            (None, None, None, None, "CIERRE MES MAYO 2026", None, None, 80_000),
            (datetime(2026, 6, 2), "EGRESO", 12, None, "Cierre de cuenta", 3, 20_000, None),
            (None, "CIERRE MES DE JUNIO DE 2026", None, None, None, None, None, 20_000),
            (datetime(2026, 7, 3), "EGRESO", 13, None, "Agua", 4, 10_000, None),
            # Cinema: el cierre trae concepto EGRESO y la etiqueta en COMPROB.
            (datetime(2026, 7, 31), "EGRESO", "CIERRE MES DE JULIO´26", *[None] * 5),
        ],
    )

    libro = leer_libro(ruta, TipoPartida.EGRESO)

    assert [p.comprobante for p in libro.partidas(Periodo(2026, 5))] == [10, 11]
    assert [p.comprobante for p in libro.partidas(Periodo(2026, 6))] == [12]
    assert [p.comprobante for p in libro.partidas(Periodo(2026, 7))] == [13]
    assert libro.periodos_cerrados == {Periodo(2026, 5), Periodo(2026, 6), Periodo(2026, 7)}
    assert libro.advertencias == []


def test_encabezado_comp_con_punto_y_monto_en_haber(tmp_path):
    ruta = _planilla(
        tmp_path,
        ("FECHA", "CONCEPTO", "COMP.", "DEPTO", "DETALLE", "DEBE", "HABER", "SALDO"),
        [
            (datetime(2026, 5, 4), "INGRESO", 1, 107, None, None, 113_648, 113_648),
            (datetime(2026, 5, 5), "INGRESO", 2, 108, None, 90_000, None, 203_648),
            (None, "CIERRE MES DE MAYO DE 2026", None, None, None, None, None, 203_648),
        ],
    )

    libro = leer_libro(ruta, TipoPartida.INGRESO)

    assert [p.monto for p in libro.partidas(Periodo(2026, 5))] == [113_648, 90_000]
    assert libro.advertencias == []


def test_monto_en_debe_y_haber_usa_la_columna_esperada_y_advierte(tmp_path):
    ruta = _planilla(
        tmp_path,
        ("FECHA", "CONCEPTO", "COMPROBANTE", "DEPTO", "DETALLE", "DEBE", "HABER", "SALDO"),
        [
            (datetime(2026, 5, 4), "INGRESO", 1, 107, None, 100_000, 5_000, None),
            (None, "CIERRE MES MAYO 2026", None, None, None, None, None, None),
        ],
    )

    libro = leer_libro(ruta, TipoPartida.INGRESO)

    assert [p.monto for p in libro.partidas(Periodo(2026, 5))] == [100_000]
    assert len(libro.advertencias) == 1
    assert "DEBE y en HABER" in libro.advertencias[0]
