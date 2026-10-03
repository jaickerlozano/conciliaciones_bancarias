"""Convierte los errores de negocio y de formato de archivos en respuestas 400 legibles.

Los mensajes vienen del motor/servicios ya redactados para el usuario final.
"""

from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.conciliaciones.servicios import ErrorConciliacion
from motor.parsers.cartolas.base import ErrorCartola
from motor.parsers.conciliacion_cliente import ErrorFormatoConciliacion
from motor.parsers.libros import ErrorFormatoPlanilla

ERRORES_DE_USUARIO = (
    ErrorConciliacion,
    ErrorCartola,
    ErrorFormatoPlanilla,
    ErrorFormatoConciliacion,
)


def manejar_excepcion(exc, context):
    if isinstance(exc, ERRORES_DE_USUARIO):
        return Response({"detail": str(exc)}, status=400)
    return exception_handler(exc, context)
