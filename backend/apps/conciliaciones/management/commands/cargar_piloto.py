"""Carga una comunidad piloto con su historia real, para probar el sistema de punta a punta.

    uv run python manage.py cargar_piloto cinema|bustos [--reiniciar] [--hasta AAAA-MM]
                                                        [--cerrar-ultimo]

Para cada piloto:
- Importa el saldo inicial desde la hoja del mes anterior al primero, en la planilla
  "CONCILIACIÓN MENSUAL" del cliente.
- Procesa los meses siguientes con las planillas y cartolas reales; confirma los cruces
  sugeridos y cierra cada mes (aplicando el redondeo que el cliente ingresó a mano, si hubo).
- El último mes queda procesado y abierto, para practicar la revisión y el cierre en el panel.

Los archivos se leen de la carpeta del piloto (fuera del repo): variable de entorno indicada en
cada piloto o, por defecto, la carpeta hermana del repo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError

from apps.comunidades.models import Banco, Comunidad, CuentaBancaria
from apps.conciliaciones import servicios
from apps.conciliaciones.models import TipoArchivo
from motor.dominio import Periodo
from motor.texto import fmt_clp


@dataclass(frozen=True)
class Piloto:
    comunidad: str
    direccion: str
    rut: str
    banco: str
    cuenta: str
    variable_carpeta: str  # variable de entorno con la carpeta de los archivos
    carpeta_por_defecto: str  # carpeta hermana del repo
    planilla: str
    hoja_apertura: str
    periodo_apertura: Periodo
    ingresos: str
    egresos: str
    cartolas: dict[Periodo, str]
    redondeos: dict[Periodo, int] = field(default_factory=dict)

    def carpeta(self) -> Path:
        valor = os.environ.get(self.variable_carpeta)
        if valor:
            return Path(valor)
        if self.variable_carpeta == "CONCILIACION_DATOS_DIR":
            return settings.CONCILIACION_DATOS_DIR
        return settings.RAIZ_REPO.parent / self.carpeta_por_defecto


PILOTOS = {
    "cinema": Piloto(
        comunidad="Comunidad Edificio Cinema",
        direccion="Linneo 6447, Las Condes",
        rut="56.039.860-3",
        banco=Banco.SANTANDER,
        cuenta="0-000-03-81745-8",
        variable_carpeta="CONCILIACION_DATOS_DIR",
        carpeta_por_defecto="cinema",
        planilla="CONCILIACIÓN  MENSUAL CINEMA.xlsm",
        hoja_apertura="DICIEMBRE'25",
        periodo_apertura=Periodo(2025, 12),
        ingresos="listado ingresos CINEMA2.xlsx",
        egresos="emitir egresos CINEMA.xlsm",
        cartolas={
            # enero viene impresa sin texto: se usa su transcripción a plantilla estándar
            Periodo(2026, 1): "cartolas_estandar/cartola_enero_2026.xlsx",
            Periodo(2026, 2): "cartola_febrero_2026.pdf",
            Periodo(2026, 3): "cartola_marzo_2026.pdf",
            Periodo(2026, 4): "cartola_abril_2026.pdf",
            Periodo(2026, 5): "cartola_mayo_2026.pdf",
        },
        redondeos={Periodo(2026, 1): 1},
    ),
    "bustos": Piloto(
        comunidad="Edificio Bustos 2166",
        direccion="",
        rut="",
        banco=Banco.BCI,
        cuenta="29845203",
        variable_carpeta="CONCILIACION_BUSTOS_DIR",
        carpeta_por_defecto="bustos",
        planilla="CONCILIACIÓN  MENSUAL BUSTOS.xlsm",
        hoja_apertura="MAYO´26",
        periodo_apertura=Periodo(2026, 5),
        ingresos="listado ingresos Bustos 2166.xlsx",
        egresos="emitir egresos BUSTOS 2166.xlsm",
        cartolas={
            Periodo(2026, 6): "cartola_junio_2026.pdf",
            Periodo(2026, 7): "cartola_julio_2026.pdf",
            Periodo(2026, 8): "cartola_agosto_2026.pdf",
        },
    ),
}


def _subir(ruta: Path) -> SimpleUploadedFile:
    return SimpleUploadedFile(ruta.name, ruta.read_bytes())


class Command(BaseCommand):
    help = "Carga una comunidad piloto (cinema o bustos) con su historia real."

    def add_arguments(self, parser):
        parser.add_argument("piloto", choices=sorted(PILOTOS))
        parser.add_argument("--reiniciar", action="store_true", help="Borra y vuelve a cargar")
        parser.add_argument("--hasta", help="Último mes a cargar (AAAA-MM); por defecto, todos")
        parser.add_argument(
            "--cerrar-ultimo", action="store_true", help="Cerrar también el último mes"
        )

    def handle(self, *args, piloto, reiniciar=False, hasta=None, cerrar_ultimo=False, **opc):
        p = PILOTOS[piloto]
        datos = p.carpeta()
        meses = sorted(p.cartolas, key=lambda x: (x.anio, x.mes))
        if hasta:
            tope = Periodo.parse(hasta)
            meses = [m for m in meses if (m.anio, m.mes) <= (tope.anio, tope.mes)]
        if not meses:
            raise CommandError("No hay meses que cargar con ese --hasta.")
        ultimo = meses[-1]
        necesarios = [p.planilla, p.ingresos, p.egresos] + [p.cartolas[m] for m in meses]
        faltan = [n for n in necesarios if not (datos / n).exists()]
        if faltan:
            raise CommandError(f"Faltan archivos en {datos}: {', '.join(faltan)}")

        comunidad, _ = Comunidad.objects.get_or_create(
            nombre=p.comunidad, defaults={"direccion": p.direccion, "rut": p.rut}
        )
        cuenta, _ = CuentaBancaria.objects.get_or_create(
            banco=p.banco, numero=p.cuenta, defaults={"comunidad": comunidad}
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
            cuenta, _subir(datos / p.planilla), p.hoja_apertura, p.periodo_apertura, None
        )
        self.stdout.write(f"{p.periodo_apertura}  saldo inicial importado")

        for periodo in meses:
            c = servicios.crear_conciliacion(cuenta, periodo, None)
            archivos = {
                TipoArchivo.INGRESOS: p.ingresos,
                TipoArchivo.EGRESOS: p.egresos,
                TipoArchivo.CARTOLA: p.cartolas[periodo],
            }
            for tipo, nombre in archivos.items():
                servicios.guardar_archivo(c, tipo, _subir(datos / nombre), None)
            servicios.procesar(c, None)
            if periodo in p.redondeos:
                servicios.ajustar_redondeo(c, p.redondeos[periodo], None)

            r = servicios.calcular_resumen(c)
            linea = (
                f"{periodo}  diferencia {fmt_clp(r.diferencia)}, "
                f"{r.cruces_por_revisar} cruces por revisar"
            )
            if periodo != ultimo or cerrar_ultimo:
                servicios.confirmar_todos(c, None)
                servicios.cerrar(c, None)
                linea += " → confirmados y cerrada"
            self.stdout.write(linea)

        self.stdout.write(self.style.SUCCESS(f"Piloto {piloto} cargado."))
