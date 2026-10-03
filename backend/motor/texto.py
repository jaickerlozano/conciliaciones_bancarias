"""Utilidades de normalización de texto y montos compartidas por los parsers."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

MESES = {
    "ENERO": 1,
    "FEBRERO": 2,
    "MARZO": 3,
    "ABRIL": 4,
    "MAYO": 5,
    "JUNIO": 6,
    "JULIO": 7,
    "AGOSTO": 8,
    "SEPTIEMBRE": 9,
    "SETIEMBRE": 9,
    "OCTUBRE": 10,
    "NOVIEMBRE": 11,
    "DICIEMBRE": 12,
}
NOMBRE_MES = {v: k.capitalize() for k, v in MESES.items() if k != "SETIEMBRE"}

_RE_MES_ANIO = re.compile(
    r"(" + "|".join(MESES) + r")\D{0,4}?(\d{4}|\d{2})(?!\d)",
)


def normalizar(texto: object) -> str:
    """Mayúsculas, sin tildes y con espacios colapsados."""
    if texto is None:
        return ""
    s = unicodedata.normalize("NFKD", str(texto))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.upper().split())


def extraer_mes_anio(texto: str) -> tuple[int, int] | None:
    """Encuentra 'MAYO 2026', "MAYO´26", 'AGOSTO2026', etc. Devuelve (anio, mes)."""
    m = _RE_MES_ANIO.search(normalizar(texto))
    if not m:
        return None
    mes = MESES[m.group(1)]
    anio = int(m.group(2))
    if anio < 100:
        anio += 2000
    return anio, mes


def a_pesos(valor: object) -> tuple[int, bool]:
    """Convierte a entero en pesos. Devuelve (monto, tenia_decimales)."""
    d = Decimal(str(valor))
    entero = int(d.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return entero, d != entero


def parse_monto_cl(texto: str) -> int:
    """'1.379.448' -> 1379448; '390.087,00' -> 390087. Ignora espacios intermedios."""
    s = texto.replace(" ", "").strip()
    negativo = s.startswith("-") or s.endswith("-")
    s = s.strip("-")
    if "," in s:
        entero, _, dec = s.partition(",")
        valor, _ = a_pesos(f"{entero.replace('.', '')}.{dec or 0}")
    else:
        valor = int(s.replace(".", ""))
    return -valor if negativo else valor


def a_fecha(valor: object) -> date | None:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return None


def fmt_clp(monto: int) -> str:
    """1379448 -> '$1.379.448' (formato chileno)."""
    signo = "-" if monto < 0 else ""
    return f"{signo}${abs(monto):,}".replace(",", ".")
