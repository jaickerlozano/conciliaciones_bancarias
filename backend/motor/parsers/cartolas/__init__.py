"""Parsers de cartolas. Importar cada módulo aquí para que se registre."""

from motor.parsers.cartolas import (  # noqa: F401
    banco_chile_pdf,
    bci_pdf,
    plantilla,
    santander_pdf,
)
from motor.parsers.cartolas.base import ErrorCartola, leer_cartola, parsers_disponibles

__all__ = ["ErrorCartola", "leer_cartola", "parsers_disponibles"]
