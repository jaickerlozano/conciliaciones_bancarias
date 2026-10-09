"""Cartola oficial Scotiabank "ESTADO DE CUENTA CORRIENTE" (PDF con texto).

Es un formato distinto del "ESTADO DE CUENTA N° <nº>" que lee `scotiabank_pdf.py`.

Particularidades del formato:
- El logo es una imagen. Se reconoce por la cabecera "ESTADO DE CUENTA CORRIENTE",
  "No. CTA. MONEDA ESTADO CTA." (cuenta con guiones, p. ej. "0-0099-28968-17"), el bloque
  y el bloque "RESUMEN DE MOVIMIENTOS" (el nombre del banco solo sale en el correo del
  ejecutivo, así que no se exige).
- Período "DESDE HASTA" con fechas "01/SEP/2026"; las filas traen solo día y mes
  ("07 / SEP"): el año se deduce del período (incluso diciembre → enero).
- Columnas FECHA | DESCRIPCION MOVIMIENTO | DOCTO No. | CARGO | ABONO | SALDO DIARIO. Cada
  palabra se asigna a su columna por la posición horizontal respecto de los encabezados, que
  se repiten en cada página. "00000000" en DOCTO significa "sin documento".
- El SALDO DIARIO puede faltar en algunas filas: cuando aparece, se comprueba que la suma de
  los movimientos desde el último saldo explique la variación.
- Resumen: saldo anterior + depósitos/abonos − cargos/giros = saldo actual.
- Al final viene "Resumen de Comisiones", que repite cargos ya listados: no son movimientos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pdfplumber

from motor.dominio import Cartola, MovimientoBancario
from motor.parsers.cartolas.banco_chile_pdf import fecha_dia_mes
from motor.parsers.cartolas.base import ErrorCartola, ParserCartola, registrar
from motor.parsers.cartolas.bci_pdf import _agrupar_lineas, _Palabra, _palabras, _texto_linea
from motor.texto import fmt_clp, parse_monto_cl

MESES_ABREV = {
    "ENE": 1,
    "FEB": 2,
    "MAR": 3,
    "ABR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AGO": 8,
    "SEP": 9,
    "SET": 9,
    "OCT": 10,
    "NOV": 11,
    "DIC": 12,
}
_RE_DIA = re.compile(r"^\d{2}$")
_RE_MONTO = re.compile(r"^-?\d{1,3}(\.\d{3})*$")
_RE_CUENTA = re.compile(
    r"No\.\s*CTA\.\s+MONEDA\s+ESTADO\s+CTA\.\s*\n\s*([\d-]+)\s+\S+\s+(\d+)", re.IGNORECASE
)
_FECHA_ABREV = r"(\d{2}/[A-Z]{3}/\d{4})"
_RE_PERIODO = re.compile(r"DESDE\s+HASTA\s*\n.*?" + _FECHA_ABREV + r"\s+" + _FECHA_ABREV)
_M = r"\s+(-?[\d.]+)"
_RE_RESUMEN = re.compile(
    r"SALDO ANTERIOR\s+DEPOSITOS/ABONOS\s+CARGOS/GIROS\s+SALDO ACTUAL\s*\n\s*(-?[\d.]+)" + _M * 3
)
# No se exige "SCOTIABANK": solo aparece en el correo del ejecutivo, que puede faltar.
_FIRMA = ("ESTADO DE CUENTA CORRIENTE", "RESUMEN DE MOVIMIENTOS", "NO. CTA. MONEDA ESTADO CTA.")
_FIN_MOVIMIENTOS = "RESUMEN DE COMISIONES"
_MARGEN = 5  # pt
_MARGEN_DOCTO = 10  # pt: el nº de documento empieza un poco a la izquierda de "DOCTO"
_ALTO_ENCABEZADO = 8  # pt: "DOCTO"/"No." y "SALDO"/"DIARIO" van media línea arriba/abajo


@dataclass
class _Columnas:
    """Límites horizontales derivados de los encabezados de la tabla de una página."""

    inicio_documento: float  # x0 de una palabra: >= esto ya no es descripción
    inicio_cargos: float  # x1 de un monto: >= esto es un monto (cargo, abono o saldo)
    inicio_abonos: float  # x1 de un monto: < esto es cargo
    inicio_saldo: float  # x1 de un monto: < esto es abono; si no, saldo diario
    top: float  # las filas de movimientos van debajo de los encabezados


def fecha_abreviada(texto: str) -> date:
    """'01/SEP/2026' -> date(2026, 9, 1)."""
    dia, mes, anio = texto.upper().split("/")
    if mes not in MESES_ABREV:
        raise ErrorCartola(f"No se reconoce el mes '{mes}' en la fecha {texto}.")
    return date(int(anio), MESES_ABREV[mes], int(dia))


def fecha_fila(dia: str, mes: str, desde: date, hasta: date) -> date:
    """'07', 'SEP' -> fecha dentro del período DESDE/HASTA (deduce el año, incluso dic → ene)."""
    mes = mes.upper()
    if mes not in MESES_ABREV:
        raise ErrorCartola(f"No se reconoce el mes '{mes}' en la fecha '{dia} / {mes}'.")
    return fecha_dia_mes(f"{dia}/{MESES_ABREV[mes]:02d}", desde, hasta)


def _error(nro_pagina: int, linea: list[_Palabra], motivo: str) -> ErrorCartola:
    return ErrorCartola(
        f"Página {nro_pagina}: línea '{_texto_linea(linea)}': {motivo}. "
        "Revise la cartola o use la plantilla estándar."
    )


def _es_movimiento(linea: list[_Palabra]) -> bool:
    """Filas '07 / SEP …': día, barra y mes abreviado como palabras separadas."""
    return (
        len(linea) >= 3
        and _RE_DIA.match(linea[0].texto) is not None
        and linea[1].texto == "/"
        and linea[2].texto.upper() in MESES_ABREV
    )


@registrar
class ScotiabankPDFCuentaCorriente(ParserCartola):
    banco = "Scotiabank"
    formato = "pdf-cuenta-corriente"
    extensiones = (".pdf",)

    @classmethod
    def puede_leer(cls, ruta: Path) -> bool:
        try:
            with pdfplumber.open(ruta) as pdf:
                primera = pdf.pages[0].extract_text() or ""
        except Exception:
            return False
        mayus = primera.upper()
        return all(f in mayus for f in _FIRMA) and _RE_CUENTA.search(primera) is not None

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
        saldo_verificado = saldo_inicial  # último saldo diario confirmado
        acumulado = 0  # variación desde ese saldo (abono +, cargo −)
        fin = False
        for nro_pagina, palabras in enumerate(paginas, start=1):
            lineas = _agrupar_lineas(palabras)
            columnas = self._columnas(lineas)
            if columnas is None:
                continue
            for linea in lineas:
                if _FIN_MOVIMIENTOS in _texto_linea(linea).upper():
                    fin = True
                    break
                if linea[0].top <= columnas.top or not _es_movimiento(linea):
                    continue
                mov, saldo = self._movimiento(linea, columnas, desde, hasta, nro_pagina)
                movimientos.append(mov)
                acumulado += -mov.monto if mov.es_cargo else mov.monto
                if saldo is not None:
                    if saldo_verificado + acumulado != saldo:
                        raise _error(
                            nro_pagina,
                            linea,
                            f"el saldo diario {fmt_clp(saldo)} no corresponde al saldo anterior "
                            f"{fmt_clp(saldo_verificado)} más los movimientos desde entonces "
                            f"({fmt_clp(acumulado)}): revise si un monto es cargo o abono",
                        )
                    saldo_verificado, acumulado = saldo, 0
            if fin:
                break

        if not movimientos:
            raise ErrorCartola(
                f"No se encontraron movimientos en '{ruta.name}'. ¿Es el estado de cuenta "
                "corriente Scotiabank completo, descargado en PDF (no escaneado)?"
            )
        advertencias: list[str] = []
        calculado = saldo_verificado + acumulado
        if calculado != saldo_final:
            advertencias.append(
                f"El saldo calculado con los movimientos ({fmt_clp(calculado)}) no coincide con "
                f"el saldo actual del resumen ({fmt_clp(saldo_final)})."
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
        periodo = _RE_PERIODO.search(texto.upper())
        if cuenta is None or periodo is None:
            raise ErrorCartola(
                f"No se encontró el nº de cuenta o el período (DESDE/HASTA) en '{ruta.name}'. "
                "¿Es el estado de cuenta corriente oficial Scotiabank?"
            )
        desde, hasta = fecha_abreviada(periodo.group(1)), fecha_abreviada(periodo.group(2))
        if desde > hasta:
            raise ErrorCartola(
                f"El período de '{ruta.name}' es inválido: {desde:%d/%m/%Y} a {hasta:%d/%m/%Y}."
            )
        return cuenta.group(1), cuenta.group(2).lstrip("0") or "0", desde, hasta

    @staticmethod
    def _resumen(texto: str, ruta: Path) -> tuple[int, int, int, int]:
        """Saldo anterior, depósitos/abonos, cargos/giros y saldo actual de la cabecera."""
        m = _RE_RESUMEN.search(texto.upper())
        if m is None:
            raise ErrorCartola(
                f"'{ruta.name}' no trae el RESUMEN DE MOVIMIENTOS completo (saldo anterior, "
                "depósitos/abonos, cargos/giros y saldo actual). ¿Está completa la cartola?"
            )
        anterior, abonos, cargos, actual = (parse_monto_cl(g) for g in m.groups())
        if anterior + abonos - cargos != actual:
            raise ErrorCartola(
                f"El resumen de '{ruta.name}' no cuadra: {fmt_clp(anterior)} + "
                f"{fmt_clp(abonos)} − {fmt_clp(cargos)} ≠ {fmt_clp(actual)}."
            )
        return anterior, abonos, cargos, actual

    @staticmethod
    def _columnas(lineas: list[list[_Palabra]]) -> _Columnas | None:
        """Ubica la fila FECHA … CARGO ABONO y, cerca de ella, "DOCTO" y "DIARIO"."""
        for i, linea in enumerate(lineas):
            enc = {p.texto.upper(): p for p in linea}
            if not {"FECHA", "CARGO", "ABONO"} <= enc.keys():
                continue
            top = enc["CARGO"].top
            cercanas = [
                p
                for vecina in lineas[max(i - 1, 0) : i + 2]
                for p in vecina
                if abs(p.top - top) <= _ALTO_ENCABEZADO
            ]
            docto = next((p for p in cercanas if p.texto.upper() == "DOCTO"), None)
            diario = next((p for p in cercanas if p.texto.upper() == "DIARIO"), None)
            if docto is None or diario is None:
                continue
            return _Columnas(
                inicio_documento=docto.x0 - _MARGEN_DOCTO,
                inicio_cargos=enc["CARGO"].x0,
                inicio_abonos=enc["ABONO"].x0,
                inicio_saldo=diario.x0 - _MARGEN,
                top=max(p.top for p in cercanas),
            )
        return None

    @staticmethod
    def _movimiento(
        linea: list[_Palabra],
        col: _Columnas,
        desde: date,
        hasta: date,
        nro_pagina: int,
    ) -> tuple[MovimientoBancario, int | None]:
        descripcion: list[str] = []
        documento: str | None = None
        montos: dict[str, int] = {}
        for p in linea[3:]:
            if p.x0 < col.inicio_documento:
                descripcion.append(p.texto)
            elif p.x1 < col.inicio_cargos and documento is None and p.texto.isdigit():
                documento = "" if p.texto.strip("0") == "" else p.texto
            elif _RE_MONTO.match(p.texto) and p.x1 >= col.inicio_cargos:
                if p.x1 < col.inicio_abonos:
                    columna = "cargo"
                elif p.x1 < col.inicio_saldo:
                    columna = "abono"
                else:
                    columna = "saldo"
                if columna in montos:
                    raise _error(nro_pagina, linea, f"dos montos en la columna {columna}")
                montos[columna] = parse_monto_cl(p.texto)
            else:
                raise _error(nro_pagina, linea, f"texto inesperado '{p.texto}'")

        if ("cargo" in montos) == ("abono" in montos):
            raise _error(nro_pagina, linea, "debe traer un cargo o un abono")
        es_cargo = "cargo" in montos
        monto = montos["cargo"] if es_cargo else montos["abono"]
        if monto <= 0:
            raise _error(nro_pagina, linea, "el monto debe ser mayor que cero")
        return (
            MovimientoBancario(
                fecha=fecha_fila(linea[0].texto, linea[2].texto, desde, hasta),
                descripcion=" ".join(descripcion),
                monto=monto,
                es_cargo=es_cargo,
                documento=documento or "",
            ),
            montos.get("saldo"),
        )
