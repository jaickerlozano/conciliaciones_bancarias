"""Cartola oficial de cuenta corriente Banco de Chile (PDF con texto, "Estado de Cuenta").

Particularidades del formato:
- Cabecera: "N° DE CUENTA : <cuenta>", "CARTOLA N° : <nº>", "DESDE : dd/mm/aaaa HASTA :
  dd/mm/aaaa". Se repite en cada página junto con los encabezados de la tabla.
- Columnas FECHA DIA/MES | DETALLE DE TRANSACCION | SUCURSAL | N° DOCTO | MONTO CHEQUES O
  CARGOS | MONTO DEPOSITOS O ABONOS | SALDO. Cada palabra se asigna a su columna por la
  posición horizontal respecto de los encabezados.
- La fecha trae solo día y mes: el año se deduce del período DESDE/HASTA (que puede cruzar
  de diciembre a enero).
- La primera fila es "SALDO INICIAL" y la última "SALDO FINAL". El SALDO solo aparece en la
  última fila de cada día: se comprueba contra la suma acumulada de los movimientos.
- La última página trae los totales DEPOSITOS | CHEQUES | OTROS ABONOS | OTROS CARGOS |
  GIROS CAJERO AUTOMATICO | IMPUESTOS, que se comparan con lo leído.
- Los nº de cheque traen ceros a la izquierda ("02962163"); el cruce los normaliza.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pdfplumber

from motor.dominio import Cartola, MovimientoBancario
from motor.parsers.cartolas.base import ErrorCartola, ParserCartola, registrar
from motor.parsers.cartolas.bci_pdf import _agrupar_lineas, _Palabra, _palabras, _texto_linea
from motor.texto import fmt_clp, parse_monto_cl

_RE_DIA_MES = re.compile(r"^\d{2}/\d{2}$")
_RE_MONTO = re.compile(r"^-?\d{1,3}(\.\d{3})*$")
_RE_CUENTA = re.compile(r"N\S{0,2}\s*DE\s+CUENTA\s*:\s*(\d+)", re.IGNORECASE)
_RE_NUMERO = re.compile(r"CARTOLA\s+N\S{0,2}\s*:\s*(\d+)", re.IGNORECASE)
_RE_PERIODO = re.compile(
    r"DESDE\s*:\s*(\d{2}/\d{2}/\d{4})\s+HASTA\s*:\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE
)
_FIRMA = ("ESTADO DE CUENTA", "DETALLE DE TRANSACCION", "MONTO CHEQUES", "MONTO DEPOSITOS")
_ENCABEZADOS = {"TRANSACCION", "SUCURSAL", "DOCTO", "CHEQUES", "DEPOSITOS", "SALDO"}
_TOTALES = ("DEPOSITOS", "CHEQUES", "OTROS", "ABONOS", "CARGOS", "IMPUESTOS")
_DESPUES_ENCABEZADO = 12  # pt: la segunda línea de encabezados ("DIA/MES", "O CARGOS")


@dataclass
class _Columnas:
    """Límites horizontales derivados de los encabezados de la tabla de una página."""

    fin_descripcion: float  # x0 de una palabra: < esto es descripción
    inicio_documento: float  # x0 de un nº: >= esto es el N° DOCTO
    inicio_cargos: float  # x1 de un monto: < inicio_abonos es cargo; < inicio_saldo, abono
    inicio_abonos: float
    inicio_saldo: float
    top: float


def fecha_dia_mes(texto: str, desde: date, hasta: date) -> date:
    """'02/10' -> fecha dentro del período DESDE/HASTA (deduce el año, incluso dic → ene)."""
    dia, mes = (int(x) for x in texto.split("/"))
    for anio in sorted({desde.year, hasta.year}):
        try:
            fecha = date(anio, mes, dia)
        except ValueError:
            continue
        if desde <= fecha <= hasta:
            return fecha
    raise ErrorCartola(
        f"La fecha {texto} está fuera del período de la cartola "
        f"({desde:%d/%m/%Y} a {hasta:%d/%m/%Y}). Revise que el archivo no esté alterado."
    )


def _error(nro_pagina: int, linea: list[_Palabra], motivo: str) -> ErrorCartola:
    return ErrorCartola(
        f"Página {nro_pagina}: línea '{_texto_linea(linea)}': {motivo}. "
        "Revise la cartola o use la plantilla estándar."
    )


def _fecha(texto: str) -> date:
    return datetime.strptime(texto, "%d/%m/%Y").date()


@registrar
class BancoChilePDF(ParserCartola):
    banco = "Banco de Chile"
    formato = "pdf-oficial"
    extensiones = (".pdf",)

    @classmethod
    def puede_leer(cls, ruta: Path) -> bool:
        try:
            with pdfplumber.open(ruta) as pdf:
                primera = pdf.pages[0].extract_text() or ""
        except Exception:
            return False
        mayus = primera.upper()
        return (
            all(f in mayus for f in _FIRMA)
            and "DIA/MES" in mayus
            and _RE_CUENTA.search(primera) is not None
        )

    def leer(self, ruta: Path) -> Cartola:
        try:
            with pdfplumber.open(ruta) as pdf:
                texto_inicial = pdf.pages[0].extract_text() or ""
                paginas = [_palabras(p) for p in pdf.pages]
        except Exception as e:
            raise ErrorCartola(f"No se pudo abrir '{ruta.name}' como PDF.") from e

        cuenta, numero, desde, hasta = self._encabezado(texto_inicial, ruta)

        movimientos: list[MovimientoBancario] = []
        saldo_inicial: int | None = None
        saldo_final: int | None = None
        acumulado = 0
        totales: tuple[int, int] | None = None
        for nro_pagina, palabras in enumerate(paginas, start=1):
            lineas = _agrupar_lineas(palabras)
            totales = self._totales(lineas) or totales
            columnas = self._columnas(lineas)
            if columnas is None:
                continue
            for linea in lineas:
                if linea[0].top <= columnas.top:
                    continue
                if _texto_linea(linea).upper().startswith("RETENCION"):
                    break  # pie de página
                if not _RE_DIA_MES.match(linea[0].texto):
                    continue
                fila = self._fila(linea, columnas, nro_pagina)
                descripcion, sucursal, documento, cargo, abono, saldo = fila

                if descripcion.upper() == "SALDO INICIAL":
                    if saldo is None or movimientos or saldo_inicial is not None:
                        raise _error(nro_pagina, linea, "SALDO INICIAL sin monto o fuera de lugar")
                    saldo_inicial = acumulado = saldo
                    continue
                if descripcion.upper() == "SALDO FINAL":
                    if saldo is None:
                        raise _error(nro_pagina, linea, "SALDO FINAL sin monto")
                    saldo_final = saldo
                    break
                if saldo_inicial is None:
                    raise _error(nro_pagina, linea, "hay movimientos antes del SALDO INICIAL")
                if (cargo is None) == (abono is None):
                    raise _error(nro_pagina, linea, "debe traer un cargo o un abono")
                es_cargo = cargo is not None
                monto = cargo if cargo is not None else abono
                assert monto is not None
                if monto <= 0:
                    raise _error(nro_pagina, linea, "el monto debe ser positivo")
                acumulado += -monto if es_cargo else monto
                if saldo is not None and saldo != acumulado:
                    raise _error(
                        nro_pagina,
                        linea,
                        f"el saldo informado es {fmt_clp(saldo)}, pero los movimientos "
                        f"leídos dan {fmt_clp(acumulado)}",
                    )
                movimientos.append(
                    MovimientoBancario(
                        fecha=fecha_dia_mes(linea[0].texto, desde, hasta),
                        descripcion=descripcion,
                        monto=monto,
                        es_cargo=es_cargo,
                        documento=documento,
                        sucursal=sucursal,
                    )
                )
            if saldo_final is not None:
                break

        if saldo_inicial is None or saldo_final is None:
            raise ErrorCartola(
                f"'{ruta.name}' no trae las filas SALDO INICIAL y SALDO FINAL. ¿Es la cartola "
                "oficial Banco de Chile completa, descargada en PDF (no escaneada)?"
            )
        if not movimientos:
            raise ErrorCartola(f"No se encontraron movimientos en '{ruta.name}'.")
        advertencias: list[str] = []
        if acumulado != saldo_final:
            advertencias.append(
                f"Los movimientos leídos llevan el saldo a {fmt_clp(acumulado)}, pero la "
                f"cartola informa un SALDO FINAL de {fmt_clp(saldo_final)}."
            )
        if totales is not None:
            total_cargos, total_abonos = totales
            cargos = sum(m.monto for m in movimientos if m.es_cargo)
            abonos = sum(m.monto for m in movimientos if not m.es_cargo)
            if (cargos, abonos) != (total_cargos, total_abonos):
                advertencias.append(
                    f"Los movimientos leídos suman cargos {fmt_clp(cargos)} y abonos "
                    f"{fmt_clp(abonos)}, pero los totales de la cartola informan cargos "
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
                f"No se encontró el nº de cuenta o el período (DESDE/HASTA) en '{ruta.name}'. "
                "¿Es la cartola oficial Banco de Chile de cuenta corriente?"
            )
        numero = _RE_NUMERO.search(texto)
        return (
            cuenta.group(1),
            numero.group(1) if numero else "",
            _fecha(periodo.group(1)),
            _fecha(periodo.group(2)),
        )

    @staticmethod
    def _totales(lineas: list[list[_Palabra]]) -> tuple[int, int] | None:
        """(cargos, abonos) de los totales de la última página, si están en estas líneas.

        Fila de rótulos DEPOSITOS | CHEQUES | OTROS ABONOS | OTROS CARGOS | GIROS CAJERO
        AUTOMATICO | IMPUESTOS seguida de una fila con exactamente seis montos.
        """
        for i, linea in enumerate(lineas[:-1]):
            textos = [p.texto for p in linea]
            if not all(t in textos for t in _TOTALES):
                continue
            siguiente = lineas[i + 1]
            if len(siguiente) == 6 and all(_RE_MONTO.match(p.texto) for p in siguiente):
                dep, cheques, otros_abonos, otros_cargos, giros, impuestos = (
                    parse_monto_cl(p.texto) for p in siguiente
                )
                return cheques + otros_cargos + giros + impuestos, dep + otros_abonos
        return None

    @staticmethod
    def _columnas(lineas: list[list[_Palabra]]) -> _Columnas | None:
        for linea in lineas:
            enc = {p.texto: p for p in linea if p.texto in _ENCABEZADOS}
            if enc.keys() < _ENCABEZADOS:
                continue
            montos = sorted((p for p in linea if p.texto == "MONTO"), key=lambda p: p.x0)
            if len(montos) != 2:
                return None
            return _Columnas(
                fin_descripcion=(enc["TRANSACCION"].x1 + enc["SUCURSAL"].x0) / 2,
                inicio_documento=enc["SUCURSAL"].x1,
                inicio_cargos=montos[0].x0,
                inicio_abonos=montos[1].x0,
                inicio_saldo=enc["SALDO"].x0,
                top=max(p.top for p in enc.values()) + _DESPUES_ENCABEZADO,
            )
        return None

    @staticmethod
    def _fila(
        linea: list[_Palabra], col: _Columnas, nro_pagina: int
    ) -> tuple[str, str, str, int | None, int | None, int | None]:
        """Descripción, sucursal, documento, cargo, abono y saldo de una fila."""
        descripcion: list[str] = []
        sucursal: list[str] = []
        documento = ""
        montos: dict[str, int] = {}
        for p in linea[1:]:
            if _RE_MONTO.match(p.texto) and p.x1 > col.inicio_cargos:
                if p.x1 < col.inicio_abonos:
                    columna = "cargo"
                elif p.x1 < col.inicio_saldo:
                    columna = "abono"
                else:
                    columna = "saldo"
                if columna in montos:
                    raise _error(nro_pagina, linea, f"dos montos en la columna {columna}")
                montos[columna] = parse_monto_cl(p.texto)
            elif p.texto.isdigit() and p.x0 >= col.inicio_documento and not documento:
                documento = p.texto
            elif p.x0 < col.fin_descripcion and not sucursal:
                descripcion.append(p.texto)
            elif p.x1 <= col.inicio_cargos and not p.texto.isdigit():
                sucursal.append(p.texto)
            else:
                raise _error(nro_pagina, linea, f"texto inesperado '{p.texto}'")
        return (
            " ".join(descripcion),
            " ".join(sucursal),
            documento,
            montos.get("cargo"),
            montos.get("abono"),
            montos.get("saldo"),
        )
