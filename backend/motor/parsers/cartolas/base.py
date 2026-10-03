"""Contrato común para los parsers de cartolas bancarias.

Cada banco/formato es una subclase de `ParserCartola` registrada con `@registrar`.
Para agregar un banco: crear un módulo en este paquete, implementar `puede_leer` y `leer`,
importarlo en `__init__.py` y agregar tests con una cartola de ejemplo.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from motor.dominio import Cartola


class ErrorCartola(ValueError):
    """La cartola no se puede leer. El mensaje se muestra tal cual al usuario."""


class ParserCartola(ABC):
    banco: ClassVar[str]
    formato: ClassVar[str]  # ej. "pdf-oficial", "excel-portal"
    extensiones: ClassVar[tuple[str, ...]]

    @classmethod
    @abstractmethod
    def puede_leer(cls, ruta: Path) -> bool:
        """Detección barata del formato (sin parsear todo el archivo)."""

    @abstractmethod
    def leer(self, ruta: Path) -> Cartola:
        """Devuelve la cartola completa o lanza ErrorCartola."""


_REGISTRO: list[type[ParserCartola]] = []


def registrar(cls: type[ParserCartola]) -> type[ParserCartola]:
    _REGISTRO.append(cls)
    return cls


def parsers_disponibles() -> list[type[ParserCartola]]:
    return list(_REGISTRO)


def leer_cartola(ruta: str | Path) -> Cartola:
    """Detecta el formato y lee la cartola. Valida que los saldos cuadren."""
    ruta = Path(ruta)
    candidatos = [
        p for p in _REGISTRO if ruta.suffix.lower() in p.extensiones and p.puede_leer(ruta)
    ]
    if not candidatos:
        formatos = ", ".join(f"{p.banco} ({p.formato})" for p in _REGISTRO)
        raise ErrorCartola(
            f"No se reconoce el formato de '{ruta.name}'. Formatos soportados: {formatos}. "
            "Si es un PDF escaneado o descargado como imagen, pida al banco la cartola oficial "
            "en PDF o el archivo Excel/CSV de movimientos."
        )
    cartola = candidatos[0]().leer(ruta)
    cartola.advertencias.extend(cartola.validar())
    return cartola
