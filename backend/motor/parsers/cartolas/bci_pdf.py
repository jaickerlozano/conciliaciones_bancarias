"""Cartola oficial de cuenta corriente BCI (PDF con texto).

Particularidades del formato:
- Encabezado: "CARTOLA DE CUENTA CORRIENTE <nº>", "Nº CUENTA :<cuenta>",
  "PERIODO : dd-mm-aaaa al dd-mm-aaaa". El nombre del banco (BCI) solo aparece en el texto
  legal de la última página.
- Columnas FECHA | SUCURSAL | DESCRIPCION | Nº DE DOCUMENTO | CHEQUES Y OTROS CARGOS |
  DEPOSITOS Y OTROS ABONOS | SALDO DIARIO, sin separadores: cada palabra se asigna a su
  columna por posición horizontal respecto de los encabezados (que se repiten en cada página).
- Cada fila trae su SALDO DIARIO. El sentido (cargo/abono) se confirma con la variación del
  saldo: saldo de la fila − saldo previo debe ser +monto (abono) o −monto (cargo).
- Las descripciones pueden traer RUT y números ("ABONO TERCEROS 16964788-7 ..."): no se
  confunden con el nº de documento porque quedan a la izquierda de su columna.
- El "Resumen del Periodo" trae: saldo anterior − total cargos + total abonos = saldo final.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pdfplumber

from motor.dominio import Cartola, MovimientoBancario
from motor.parsers.cartolas.base import ErrorCartola, ParserCartola, registrar
from motor.texto import fmt_clp, parse_monto_cl

_RE_FECHA = re.compile(r"^\d{2}-\d{2}-\d{4}$")
_RE_MONTO = re.compile(r"^\d{1,3}(\.\d{3})*$")
_RE_CUENTA = re.compile(r"N[º°o]\s*CUENTA\s*:\s*(\d+)", re.IGNORECASE)
_RE_NUMERO = re.compile(r"CARTOLA DE CUENTA CORRIENTE\s+(\d+)")
_RE_PERIODO = re.compile(r"(\d{2}-\d{2}-\d{4})\s+al\s+(\d{2}-\d{2}-\d{4})")
_ENCABEZADOS = {"SUCURSAL", "DESCRIPCION", "DOCUMENTO", "CARGOS", "ABONOS", "DIARIO"}
_TOLERANCIA_LINEA = 3  # pt: palabras con 'top' a esta distancia pertenecen a la misma línea
_TOLERANCIA_RESUMEN = 6  # pt: los montos del resumen vienen escalonados verticalmente
_MARGEN = 5  # pt


@dataclass
class _Palabra:
    texto: str
    x0: float
    x1: float
    top: float


@dataclass
class _Columnas:
    """Límites horizontales derivados de los encabezados de la tabla de una página."""

    fin_sucursal: float  # x0 de una palabra: < esto es sucursal
    inicio_documento: float  # x0 de una palabra: >= esto ya no es descripción
    fin_documento: float
    x1_cargos: float  # borde derecho de cada columna de montos (alineados a la derecha)
    x1_abonos: float
    x1_saldo: float
    top: float  # las filas de movimientos van debajo de los encabezados


def _fecha(texto: str) -> date:
    return datetime.strptime(texto, "%d-%m-%Y").date()


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


def _texto_linea(linea: list[_Palabra]) -> str:
    return " ".join(p.texto for p in linea)


@registrar
class BciPDFOficial(ParserCartola):
    banco = "BCI"
    formato = "pdf-oficial"
    extensiones = (".pdf",)

    @classmethod
    def puede_leer(cls, ruta: Path) -> bool:
        try:
            with pdfplumber.open(ruta) as pdf:
                primera = (pdf.pages[0].extract_text() or "").upper()
                ultima = (pdf.pages[-1].extract_text() or "").upper()
        except Exception:
            return False
        return (
            "CARTOLA DE CUENTA CORRIENTE" in primera
            and "SALDO DIARIO" in primera
            and re.search(r"\bBCI\b", ultima) is not None
        )

    def leer(self, ruta: Path) -> Cartola:
        try:
            with pdfplumber.open(ruta) as pdf:
                texto_inicial = pdf.pages[0].extract_text() or ""
                paginas = [_palabras(p) for p in pdf.pages]
        except Exception as e:
            raise ErrorCartola(f"No se pudo abrir '{ruta.name}' como PDF.") from e

        cuenta, numero, desde, hasta = self._encabezado(texto_inicial, ruta)
        saldo_inicial, total_cargos, total_abonos, saldo_final = self._resumen(paginas, ruta)

        movimientos: list[MovimientoBancario] = []
        saldo_previo = saldo_inicial
        for nro_pagina, palabras in enumerate(paginas, start=1):
            lineas = _agrupar_lineas(palabras)
            columnas = self._columnas(lineas)
            if columnas is None:
                continue
            for linea in lineas:
                if linea[0].top <= columnas.top:
                    continue
                texto = _texto_linea(linea)
                if texto.upper().startswith("RESUMEN DEL PERIODO"):
                    break
                if not _RE_FECHA.match(linea[0].texto):
                    continue
                mov, saldo_fila = self._movimiento(linea, columnas, saldo_previo, nro_pagina)
                movimientos.append(mov)
                saldo_previo = saldo_fila

        if not movimientos:
            raise ErrorCartola(
                f"No se encontraron movimientos en '{ruta.name}'. ¿Es la cartola oficial BCI "
                "completa, descargada en PDF (no escaneada)?"
            )
        advertencias: list[str] = []
        if saldo_previo != saldo_final:
            advertencias.append(
                f"El saldo del último movimiento ({fmt_clp(saldo_previo)}) no coincide con el "
                f"saldo final del resumen ({fmt_clp(saldo_final)})."
            )
        cargos = sum(m.monto for m in movimientos if m.es_cargo)
        abonos = sum(m.monto for m in movimientos if not m.es_cargo)
        if (cargos, abonos) != (total_cargos, total_abonos):
            advertencias.append(
                f"Los movimientos leídos suman cargos {fmt_clp(cargos)} y abonos "
                f"{fmt_clp(abonos)}, pero el resumen de la cartola informa cargos "
                f"{fmt_clp(total_cargos)} y abonos {fmt_clp(total_abonos)}. "
                "Revise que la cartola esté completa."
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
    def _encabezado(texto: str, ruta: Path) -> tuple[str, str, date, date]:
        cuenta = _RE_CUENTA.search(texto)
        periodo = _RE_PERIODO.search(texto)
        if cuenta is None or periodo is None:
            raise ErrorCartola(
                f"No se encontró el nº de cuenta o el período en '{ruta.name}'. "
                "¿Es la cartola oficial BCI de cuenta corriente?"
            )
        numero = _RE_NUMERO.search(texto)
        return (
            cuenta.group(1),
            numero.group(1) if numero else "",
            _fecha(periodo.group(1)),
            _fecha(periodo.group(2)),
        )

    @staticmethod
    def _resumen(paginas: list[list[_Palabra]], ruta: Path) -> tuple[int, int, int, int]:
        """Saldo anterior, total cargos, total abonos y saldo final del 'Resumen del Periodo'."""
        for palabras in paginas:
            lineas = _agrupar_lineas(palabras)
            inicio = next(
                (
                    linea[0].top
                    for linea in lineas
                    if _texto_linea(linea).upper().startswith("RESUMEN DEL PERIODO")
                ),
                None,
            )
            if inicio is None:
                continue
            # la fila del resumen empieza con "dd-mm-aaaa al dd-mm-aaaa"
            fila = next(
                (
                    p
                    for p in sorted(palabras, key=lambda p: (p.top, p.x0))
                    if p.top > inicio and _RE_FECHA.match(p.texto)
                ),
                None,
            )
            if fila is None:
                break
            montos = sorted(
                (
                    p
                    for p in palabras
                    if abs(p.top - fila.top) <= _TOLERANCIA_RESUMEN and _RE_MONTO.match(p.texto)
                ),
                key=lambda p: p.x0,
            )
            if len(montos) != 4:
                break
            anterior, cargos, abonos, final = (parse_monto_cl(p.texto) for p in montos)
            if anterior - cargos + abonos != final:
                raise ErrorCartola(
                    f"El resumen de '{ruta.name}' no cuadra: {fmt_clp(anterior)} − "
                    f"{fmt_clp(cargos)} + {fmt_clp(abonos)} ≠ {fmt_clp(final)}."
                )
            return anterior, cargos, abonos, final
        raise ErrorCartola(
            f"'{ruta.name}' no trae un 'Resumen del Periodo' legible "
            "(saldo anterior, cargos, abonos y saldo final). ¿Está completa la cartola?"
        )

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
        return _Columnas(
            fin_sucursal=enc["SUCURSAL"].x1,
            inicio_documento=enc["DOCUMENTO"].x0 - _MARGEN,
            fin_documento=enc["DOCUMENTO"].x1 + _MARGEN,
            x1_cargos=enc["CARGOS"].x1,
            x1_abonos=enc["ABONOS"].x1,
            x1_saldo=enc["DIARIO"].x1,
            top=max(p.top for p in enc.values()),
        )

    @staticmethod
    def _movimiento(
        linea: list[_Palabra], col: _Columnas, saldo_previo: int, nro_pagina: int
    ) -> tuple[MovimientoBancario, int]:
        texto = _texto_linea(linea)

        def error(motivo: str) -> ErrorCartola:
            return ErrorCartola(
                f"Página {nro_pagina}: no se pudo leer la línea '{texto}' ({motivo}). "
                "Revise la cartola o use la plantilla estándar."
            )

        sucursal, descripcion, documento = [], [], ""
        montos: dict[str, int] = {}
        for p in linea[1:]:
            if p.x0 < col.fin_sucursal and not descripcion:
                sucursal.append(p.texto)
            elif p.x0 < col.inicio_documento:
                descripcion.append(p.texto)
            elif not documento and p.x1 <= col.fin_documento and p.texto.isdigit():
                documento = p.texto
            elif _RE_MONTO.match(p.texto):
                distancias = {
                    "cargo": abs(p.x1 - col.x1_cargos),
                    "abono": abs(p.x1 - col.x1_abonos),
                    "saldo": abs(p.x1 - col.x1_saldo),
                }
                columna = min(distancias, key=distancias.__getitem__)
                if columna in montos:
                    raise error(f"dos montos en la columna {columna}")
                montos[columna] = parse_monto_cl(p.texto)
            else:
                raise error(f"texto inesperado '{p.texto}'")

        if "saldo" not in montos:
            raise error("falta el saldo diario")
        if ("cargo" in montos) == ("abono" in montos):
            raise error("debe traer un cargo o un abono")
        es_cargo = "cargo" in montos
        monto = montos["cargo"] if es_cargo else montos["abono"]
        saldo = montos["saldo"]
        variacion = saldo - saldo_previo
        if variacion != (-monto if es_cargo else monto):
            raise error(
                f"el saldo pasa de {fmt_clp(saldo_previo)} a {fmt_clp(saldo)}, "
                f"lo que no corresponde a un {'cargo' if es_cargo else 'abono'} "
                f"de {fmt_clp(monto)}"
            )
        return (
            MovimientoBancario(
                fecha=_fecha(linea[0].texto),
                descripcion=" ".join(descripcion),
                monto=monto,
                es_cargo=es_cargo,
                documento=documento,
                sucursal=" ".join(sucursal),
            ),
            saldo,
        )
