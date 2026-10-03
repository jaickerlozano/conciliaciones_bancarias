"""Cartola oficial de cuenta corriente Banco Santander Chile (PDF con texto).

Particularidades del formato:
- Columnas FECHA | SUCURSAL | DESCRIPCION | N° DCTO | CARGOS | ABONOS | SALDO, sin separadores:
  la columna de cada monto se determina por su posición horizontal (los montos van alineados
  a la derecha bajo su encabezado).
- Algunos montos vienen con los caracteres separados ("3 9 8 . 153"), por lo que se unen las
  palabras numéricas contiguas.
- Las fechas son dd/mm; el año se deduce del rango DESDE/HASTA de la cartola.
- El saldo solo aparece en el último movimiento de cada día.
- El resumen final trae SALDO INICIAL ... SALDO FINAL.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pdfplumber

from motor.dominio import Cartola, MovimientoBancario
from motor.parsers.cartolas.base import ErrorCartola, ParserCartola, registrar
from motor.texto import parse_monto_cl

_RE_FECHA_LINEA = re.compile(r"^\d{2}/\d{2}$")
_RE_FECHA_COMPLETA = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_RE_NUMERICO = re.compile(r"^[\d.,\-]+$")
_ENCABEZADOS = {"SUCURSAL", "N°", "DCTO", "CARGOS", "ABONOS", "SALDO"}
_TOLERANCIA_LINEA = 3  # pt: palabras con 'top' a esta distancia pertenecen a la misma línea
_GAP_UNION = 1.5  # pt: palabras numéricas más cercanas que esto forman un solo monto


@dataclass
class _Palabra:
    texto: str
    x0: float
    x1: float
    top: float


@dataclass
class _Columnas:
    """Límites horizontales derivados de los encabezados de la tabla."""

    fin_sucursal: float
    inicio_documento: float
    fin_documento: float
    limite_cargo_abono: float  # x1 de un monto: <= esto es cargo
    limite_abono_saldo: float  # x1 de un monto: <= esto es abono, si no es saldo


def _palabras(pagina) -> list[_Palabra]:
    return [
        _Palabra(w["text"], w["x0"], w["x1"], w["top"])
        for w in pagina.extract_words(keep_blank_chars=False, use_text_flow=False)
    ]


def _agrupar_lineas(palabras: list[_Palabra]) -> list[list[_Palabra]]:
    lineas: list[list[_Palabra]] = []
    for p in sorted(palabras, key=lambda p: (p.top, p.x0)):
        if lineas and abs(lineas[-1][0].top - p.top) <= _TOLERANCIA_LINEA:
            lineas[-1].append(p)
        else:
            lineas.append([p])
    return [sorted(linea, key=lambda p: p.x0) for linea in lineas]


def _unir_numeros(linea: list[_Palabra]) -> list[_Palabra]:
    """Une '3','9','8','.','153' contiguos en '398.153'."""
    resultado: list[_Palabra] = []
    for p in linea:
        previo = resultado[-1] if resultado else None
        if (
            previo is not None
            and _RE_NUMERICO.match(p.texto)
            and _RE_NUMERICO.match(previo.texto)
            and p.x0 - previo.x1 <= _GAP_UNION
        ):
            resultado[-1] = _Palabra(previo.texto + p.texto, previo.x0, p.x1, previo.top)
        else:
            resultado.append(p)
    return resultado


def _texto_linea(linea: list[_Palabra]) -> str:
    return " ".join(p.texto for p in linea)


@registrar
class SantanderPDFOficial(ParserCartola):
    banco = "Santander"
    formato = "pdf-oficial"
    extensiones = (".pdf",)

    @classmethod
    def puede_leer(cls, ruta: Path) -> bool:
        try:
            with pdfplumber.open(ruta) as pdf:
                texto = (pdf.pages[0].extract_text() or "").upper()
        except Exception:
            return False
        return "SANTANDER" in texto.replace(" ", "") and "DETALLE DE MOVIMIENTOS" in texto

    def leer(self, ruta: Path) -> Cartola:
        with pdfplumber.open(ruta) as pdf:
            paginas = [_agrupar_lineas(_palabras(p)) for p in pdf.pages]

        cuenta, numero, desde, hasta = self._encabezado(paginas[0])
        movimientos: list[MovimientoBancario] = []
        advertencias: list[str] = []
        saldo_inicial = saldo_final = None

        for nro_pagina, lineas in enumerate(paginas, start=1):
            columnas = self._columnas(lineas)
            for i, linea in enumerate(lineas):
                if columnas and _RE_FECHA_LINEA.match(linea[0].texto):
                    mov = self._movimiento(_unir_numeros(linea), columnas, desde, hasta)
                    if mov is None:
                        advertencias.append(
                            f"Página {nro_pagina}: no se pudo leer la línea "
                            f"'{_texto_linea(linea)}'."
                        )
                    else:
                        movimientos.append(mov)
                elif "SALDO INICIAL" in _texto_linea(linea) and i + 1 < len(lineas):
                    resumen = [p.texto for p in _unir_numeros(lineas[i + 1])]
                    try:
                        saldo_inicial = parse_monto_cl(resumen[0])
                        saldo_final = parse_monto_cl(resumen[-1])
                    except (ValueError, IndexError) as e:
                        raise ErrorCartola(
                            f"No se pudo leer el resumen de saldos de '{ruta.name}'."
                        ) from e

        if saldo_inicial is None or saldo_final is None:
            raise ErrorCartola(
                f"'{ruta.name}' no trae el resumen 'SALDO INICIAL … SALDO FINAL'. "
                "¿Está completa la cartola?"
            )
        return Cartola(
            banco=self.banco,
            cuenta=cuenta,
            numero=numero,
            desde=desde,
            hasta=hasta,
            saldo_inicial=saldo_inicial,
            saldo_final=saldo_final,
            movimientos=movimientos,
            advertencias=advertencias,
        )

    @staticmethod
    def _encabezado(lineas: list[list[_Palabra]]) -> tuple[str, str, date, date]:
        cuenta = ""
        for i, linea in enumerate(lineas):
            textos = [p.texto for p in linea]
            if "CUENTA" in textos and "CORRIENTE" in textos and i + 1 < len(lineas):
                cuenta = lineas[i + 1][0].texto
            fechas = [t for t in textos if _RE_FECHA_COMPLETA.match(t)]
            if len(fechas) >= 2:
                desde = date(*reversed([int(x) for x in fechas[0].split("/")]))
                hasta = date(*reversed([int(x) for x in fechas[1].split("/")]))
                idx = textos.index(fechas[0])
                numero = textos[idx - 1] if idx > 0 else ""
                return cuenta, numero, desde, hasta
        raise ErrorCartola("No se encontró el período (DESDE/HASTA) en la cartola Santander.")

    @staticmethod
    def _columnas(lineas: list[list[_Palabra]]) -> _Columnas | None:
        enc: dict[str, _Palabra] = {}
        for linea in lineas:
            for p in linea:
                if p.texto in _ENCABEZADOS and p.texto not in enc:
                    enc[p.texto] = p
            if enc.keys() >= _ENCABEZADOS:
                break
        else:
            return None
        cargos, abonos, saldo = enc["CARGOS"], enc["ABONOS"], enc["SALDO"]
        return _Columnas(
            fin_sucursal=enc["SUCURSAL"].x1 + 10,
            inicio_documento=enc["N°"].x0 - 5,
            fin_documento=enc["DCTO"].x1 + 10,
            limite_cargo_abono=(cargos.x1 + abonos.x1) / 2,
            limite_abono_saldo=(abonos.x1 + saldo.x1) / 2,
        )

    @staticmethod
    def _movimiento(
        linea: list[_Palabra], col: _Columnas, desde: date, hasta: date
    ) -> MovimientoBancario | None:
        dia, mes = (int(x) for x in linea[0].texto.split("/"))
        anio = hasta.year if mes <= hasta.month or desde.year == hasta.year else desde.year
        fecha = date(anio, mes, dia)

        sucursal, descripcion, documento = [], [], ""
        cargo = abono = None
        for p in linea[1:]:
            if p.x1 <= col.fin_sucursal:
                sucursal.append(p.texto)
            elif p.x0 < col.inicio_documento:
                descripcion.append(p.texto)
            elif not documento and p.x1 <= col.fin_documento and p.texto.isdigit():
                documento = p.texto
            elif _RE_NUMERICO.match(p.texto):
                if p.x1 <= col.limite_cargo_abono:
                    cargo = parse_monto_cl(p.texto)
                elif p.x1 <= col.limite_abono_saldo:
                    abono = parse_monto_cl(p.texto)
                # columna SALDO: se ignora, se valida con el resumen final
            else:
                descripcion.append(p.texto)

        if (cargo is None) == (abono is None):
            return None
        return MovimientoBancario(
            fecha=fecha,
            descripcion=" ".join(descripcion),
            monto=cargo if cargo is not None else abono,
            es_cargo=cargo is not None,
            documento=documento,
            sucursal=" ".join(sucursal),
        )
