"""Carga el piloto: Comunidad Edificio Cinema con la historia de enero a mayo 2026.

    uv run python manage.py demo_cinema [--reiniciar] [--hasta 2026-05] [--cerrar-ultimo]

- Diciembre 2025: saldo inicial importado desde la planilla de conciliación del cliente.
- Enero → abril: procesados con el programa, cruces sugeridos confirmados y cerrados
  (enero lleva el redondeo de $1 que el cliente ingresó a mano).
- Mayo: queda procesado y abierto, para practicar confirmar cruces y cerrar desde la interfaz.

Las cartolas de enero, marzo y abril vienen en formatos que el sistema no lee; se usan sus
versiones en plantilla estándar (carpeta cartolas_estandar/ de los datos del cliente).
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

PLANILLA = "CONCILIACIÓN  MENSUAL CINEMA.xlsm"
INGRESOS = "listado ingresos CINEMA2.xlsx"
EGRESOS = "emitir egresos CINEMA.xlsm"
CARTOLAS = {
    Periodo(2026, 1): "cartolas_estandar/cartola_enero_2026.xlsx",
    Periodo(2026, 2): "cartola_febrero_2026.pdf",
    Periodo(2026, 3): "cartolas_estandar/cartola_marzo_2026.xlsx",
    Periodo(2026, 4): "cartolas_estandar/cartola_abril_2026.xlsx",
    Periodo(2026, 5): "cartola_mayo_2026.pdf",
}
REDONDEOS = {Periodo(2026, 1): 1}  # ingresados a mano por el cliente en su planilla


def _subir(ruta: Path) -> SimpleUploadedFile:
    return SimpleUploadedFile(ruta.name, ruta.read_bytes())


class Command(BaseCommand):
    help = "Carga la comunidad piloto (Cinema) con la historia de enero a mayo 2026."

    def add_arguments(self, parser):
        parser.add_argument("--reiniciar", action="store_true", help="Borra y vuelve a cargar")
        parser.add_argument("--hasta", default="2026-05", help="Último mes a cargar (AAAA-MM)")
        parser.add_argument(
            "--cerrar-ultimo", action="store_true", help="Cerrar también el último mes"
        )

    def handle(self, *args, reiniciar=False, hasta="2026-05", cerrar_ultimo=False, **opciones):
        datos: Path = settings.CONCILIACION_DATOS_DIR
        ultimo = Periodo.parse(hasta)
        meses = [p for p in CARTOLAS if (p.anio, p.mes) <= (ultimo.anio, ultimo.mes)]
        necesarios = [PLANILLA, INGRESOS, EGRESOS] + [CARTOLAS[p] for p in meses]
        faltan = [n for n in necesarios if not (datos / n).exists()]
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
            cuenta, _subir(datos / PLANILLA), "DICIEMBRE'25", Periodo(2025, 12), None
        )
        self.stdout.write("2025-12  saldo inicial importado")

        for periodo in meses:
            c = servicios.crear_conciliacion(cuenta, periodo, None)
            archivos = {
                TipoArchivo.INGRESOS: INGRESOS,
                TipoArchivo.EGRESOS: EGRESOS,
                TipoArchivo.CARTOLA: CARTOLAS[periodo],
            }
            for tipo, nombre in archivos.items():
                servicios.guardar_archivo(c, tipo, _subir(datos / nombre), None)
            servicios.procesar(c, None)
            if periodo in REDONDEOS:
                servicios.ajustar_redondeo(c, REDONDEOS[periodo], None)

            r = servicios.calcular_resumen(c)
            linea = (
                f"{periodo}  diferencia {fmt_clp(r.diferencia)}, "
                f"{r.cruces_por_revisar} cruces por revisar"
            )
            if periodo != ultimo or cerrar_ultimo:
                for cruce in c.cruces.select_related("partida", "movimiento"):
                    if cruce.requiere_revision:
                        servicios.confirmar_cruce(cruce, None)
                servicios.cerrar(c, None)
                linea += " → confirmados y cerrada"
            self.stdout.write(linea)

        self.stdout.write(self.style.SUCCESS("Piloto cargado."))
