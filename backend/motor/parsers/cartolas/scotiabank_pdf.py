"""Cartola oficial de cuenta corriente Scotiabank (PDF con texto, "ESTADO DE CUENTA").

Particularidades del formato:
- El logo es una imagen: el nombre del banco no aparece en el texto. Se reconoce por la
  cabecera "ESTADO DE CUENTA N° <nº>", "Número Cuenta <cuenta>" y el resumen con los rótulos
  "Saldo Anterior", "Depositos / Abonos", "Cargos / Giros" y "Saldo Actual".
- Columnas Fecha | Descripción | N° Doc. | Cargos | Abonos | Saldo. Los montos vienen con "$"
  como palabra aparte y con signo ("$ -6.867" en Cargos). Cada palabra se asigna a su columna
  por la posición horizontal respecto de los encabezados.
- Cada fila trae su saldo: el sentido (cargo/abono) se confirma con la variación del saldo.
- "N° Doc." casi siempre es 0, que significa "sin documento".
- Resumen: saldo anterior + depósitos/abonos − cargos/giros = saldo actual.
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

_RE_FECHA = re.compile(r"^\d{2}-\d{2}-\d{4}$")
_RE_MONTO = re.compile(r"^-?\d{1,3}(\.\d{3})*$")
_RE_NUMERO = re.compile(r"ESTADO DE CUENTA N\S{0,2}\s*(\d+)", re.IGNORECASE)
_RE_CUENTA = re.compile(r"N\S{0,2}mero\s+Cuenta\s+(\d+)", re.IGNORECASE)
_RE_PERIODO = re.compile(r"Desde\s+(\d{2}-\d{2}-\d{4})\s+Hasta\s+(\d{2}-\d{2}-\d{4})", re.I)
_MONTO_RESUMEN = r"\s*\$\s*(-?[\d.]+)"
_RE_RESUMEN = {
    "anterior": re.compile(r"Saldo Anterior" + _MONTO_RESUMEN, re.IGNORECASE),
    "abonos": re.compile(r"Depositos\s*/\s*Abonos" + _MONTO_RESUMEN, re.IGNORECASE),
    "cargos": re.compile(r"Cargos\s*/\s*Giros" + _MONTO_RESUMEN, re.IGNORECASE),
    "actual": re.compile(r"Saldo Actual" + _MONTO_RESUMEN, re.IGNORECASE),
}
_FIRMA = ("ESTADO DE CUENTA N", "SALDO ANTERIOR", "DEPOSITOS / ABONOS", "CARGOS / GIROS")
_ENCABEZADOS = {"Fecha", "Doc.", "Cargos", "Abonos", "Saldo"}
_MARGEN = 5  # pt


@dataclass
class _Columnas:
    """Límites horizontales derivados de los encabezados de la tabla de una página."""

    inicio_documento: float  # x0 de una palabra: >= esto ya no es descripción
    inicio_cargos: float  # x1 de un monto: < inicio_abonos es cargo; < inicio_saldo, abono
    inicio_abonos: float
    inicio_saldo: float
    top: float


def monto_con_signo(texto: str) -> int:
    """'$ -6.867' -> -6867; '$ 1.986.523' -> 1986523."""
    return parse_monto_cl(texto.replace("$", ""))


def _fecha(texto: str) -> date:
    return datetime.strptime(texto, "%d-%m-%Y").date()


@registrar
class ScotiabankPDF(ParserCartola):
    banco = "Scotiabank"
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
            and "SALDO ACTUAL" in mayus
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
        saldo_inicial, total_abonos, total_cargos, saldo_final = self._resumen(texto_inicial, ruta)

        movimientos: list[MovimientoBancario] = []
        saldo_previo = saldo_inicial
        for nro_pagina, palabras in enumerate(paginas, start=1):
            lineas = _agrupar_lineas(palabras)
            columnas = self._columnas(lineas)
            if columnas is None:
                continue
            for linea in lineas:
                if linea[0].top <= columnas.top or not _RE_FECHA.match(linea[0].texto):
                    continue
                mov, saldo_fila = self._movimiento(linea, columnas, saldo_previo, nro_pagina)
                movimientos.append(mov)
                saldo_previo = saldo_fila

        if not movimientos:
            raise ErrorCartola(
                f"No se encontraron movimientos en '{ruta.name}'. ¿Es el estado de cuenta "
                "Scotiabank completo, descargado en PDF (no escaneado)?"
            )
        advertencias: list[str] = []
        if saldo_previo != saldo_final:
            advertencias.append(
                f"El saldo del último movimiento ({fmt_clp(saldo_previo)}) no coincide con el "
                f"saldo actual del resumen ({fmt_clp(saldo_final)})."
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
                f"No se encontró el nº de cuenta o el período (Desde/Hasta) en '{ruta.name}'. "
                "¿Es el estado de cuenta oficial Scotiabank?"
            )
        numero = _RE_NUMERO.search(texto)
        return (
            cuenta.group(1),
            numero.group(1) if numero else "",
            _fecha(periodo.group(1)),
            _fecha(periodo.group(2)),
        )

    @staticmethod
    def _resumen(texto: str, ruta: Path) -> tuple[int, int, int, int]:
        """Saldo anterior, depósitos/abonos, cargos/giros y saldo actual de la cabecera."""
        valores = {}
        for clave, patron in _RE_RESUMEN.items():
            m = patron.search(texto)
            if m is None:
                raise ErrorCartola(
                    f"'{ruta.name}' no trae el resumen completo (Saldo Anterior, Depositos / "
                    "Abonos, Cargos / Giros y Saldo Actual). ¿Está completa la cartola?"
                )
            valores[clave] = monto_con_signo(m.group(1))
        anterior, abonos, cargos, actual = (
            valores["anterior"],
            valores["abonos"],
            valores["cargos"],
            valores["actual"],
        )
        if anterior + abonos - cargos != actual:
            raise ErrorCartola(
                f"El resumen de '{ruta.name}' no cuadra: {fmt_clp(anterior)} + "
                f"{fmt_clp(abonos)} − {fmt_clp(cargos)} ≠ {fmt_clp(actual)}."
            )
        return anterior, abonos, cargos, actual

    @staticmethod
    def _columnas(lineas: list[list[_Palabra]]) -> _Columnas | None:
        for linea in lineas:
            enc = {p.texto: p for p in linea if p.texto in _ENCABEZADOS}
            if enc.keys() >= _ENCABEZADOS:
                # "N°" va justo antes de "Doc."; se toma la palabra previa si existe
                doc = enc["Doc."]
                previas = [p for p in linea if p.x1 <= doc.x0 and doc.x0 - p.x1 < _MARGEN]
                inicio_doc = min([doc.x0, *(p.x0 for p in previas)])
                return _Columnas(
                    inicio_documento=inicio_doc - _MARGEN,
                    inicio_cargos=enc["Cargos"].x0,
                    inicio_abonos=enc["Abonos"].x0,
                    inicio_saldo=enc["Saldo"].x0,
                    top=doc.top,
                )
        return None

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

        descripcion: list[str] = []
        documento = ""
        montos: dict[str, int] = {}
        for p in linea[1:]:
            if p.x0 < col.inicio_documento:
                descripcion.append(p.texto)
            elif p.texto == "$":
                continue
            elif p.x1 < col.inicio_cargos and p.texto.isdigit() and not documento:
                documento = "" if p.texto.strip("0") == "" else p.texto
            elif _RE_MONTO.match(p.texto) and p.x1 >= col.inicio_cargos:
                if p.x1 < col.inicio_abonos:
                    columna = "cargo"
                elif p.x1 < col.inicio_saldo:
                    columna = "abono"
                else:
                    columna = "saldo"
                if columna in montos:
                    raise error(f"dos montos en la columna {columna}")
                montos[columna] = monto_con_signo(p.texto)
            else:
                raise error(f"texto inesperado '{p.texto}'")

        if "saldo" not in montos:
            raise error("falta el saldo")
        if ("cargo" in montos) == ("abono" in montos):
            raise error("debe traer un cargo o un abono")
        es_cargo = "cargo" in montos
        monto = abs(montos["cargo"] if es_cargo else montos["abono"])
        if monto == 0:
            raise error("el monto es cero")
        saldo = montos["saldo"]
        if saldo - saldo_previo != (-monto if es_cargo else monto):
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
            ),
            saldo,
        )
