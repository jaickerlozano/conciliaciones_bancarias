"""Parsers de cartolas. Importar cada módulo aquí para que se registre."""

from motor.parsers.cartolas import santander_pdf  # noqa: F401
from motor.parsers.cartolas.base import ErrorCartola, leer_cartola, parsers_disponibles

__all__ = ["ErrorCartola", "leer_cartola", "parsers_disponibles"]
