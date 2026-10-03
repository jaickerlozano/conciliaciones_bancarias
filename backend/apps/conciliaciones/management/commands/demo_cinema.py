"""Carga el piloto: Comunidad Edificio Cinema, saldo inicial de abril 2026 y mayo 2026 procesado.

    uv run python manage.py demo_cinema

Usa los archivos reales de CONCILIACION_DATOS_DIR. Es idempotente: si ya existe, no hace nada
(usar --reiniciar para borrar las conciliaciones de la cuenta y volver a cargar).
"""

from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError

from apps.comunidades.models import Banco, Comunidad, CuentaBancaria
from apps.conciliaciones import servicios
from apps.conciliaciones.models import TipoArchivo
from motor.dominio import Periodo
from motor.texto import fmt_clp

ARCHIVOS = {
    "apertura": "CONCILIACIÓN  MENSUAL CINEMA.xlsm",
    TipoArchivo.INGRESOS: "listado ingresos CINEMA2.xlsx",
    TipoArchivo.EGRESOS: "emitir egresos CINEMA.xlsm",
    TipoArchivo.CARTOLA: "cartola_mayo_2026.pdf",
}


def _subir(ruta: Path) -> SimpleUploadedFile:
    return SimpleUploadedFile(ruta.name, ruta.read_bytes())


class Command(BaseCommand):
    help = "Carga la comunidad piloto (Cinema) con abril 2026 importado y mayo 2026 procesado."

    def add_arguments(self, parser):
        parser.add_argument("--reiniciar", action="store_true")

    def handle(self, *args, reiniciar=False, **opciones):
        datos: Path = settings.CONCILIACION_DATOS_DIR
        faltan = [n for n in ARCHIVOS.values() if not (datos / n).exists()]
        if faltan:
            raise CommandError(f"Faltan archivos en {datos}: {', '.join(faltan)}")

        comunidad, _ = Comunidad.objects.get_or_create(
            nombre="Comunidad Edificio Cinema",
            defaults={"direccion": "Linneo 6447, Las Condes", "rut": "56.039.860-3"},
        )
        cuenta, _ = CuentaBancaria.objects.get_or_create(
            banco=Banco.SANTANDER, numero="0-000-03-81745-8", defaults={"comunidad": comunidad}
        )
        if cuenta.conciliaciones.exists():
            if not reiniciar:
                self.stdout.write(
                    "La cuenta ya tiene conciliaciones. Use --reiniciar para recargar."
                )
                return
            for c in cuenta.conciliaciones.order_by("-anio", "-mes"):
                servicios.eliminar_sin_validar(c)

        servicios.importar_apertura(
            cuenta, _subir(datos / ARCHIVOS["apertura"]), "ABRIL´26", Periodo(2026, 4), None
        )
        mayo = servicios.crear_conciliacion(cuenta, Periodo(2026, 5), None)
        for tipo in (TipoArchivo.INGRESOS, TipoArchivo.EGRESOS, TipoArchivo.CARTOLA):
            servicios.guardar_archivo(mayo, tipo, _subir(datos / ARCHIVOS[tipo]), None)
        servicios.procesar(mayo, None)

        r = servicios.calcular_resumen(mayo)
        self.stdout.write(
            self.style.SUCCESS(
                f"Mayo 2026 procesado: diferencia {fmt_clp(r.diferencia)}, "
                f"{r.cruces_por_revisar} cruces por revisar."
            )
        )
