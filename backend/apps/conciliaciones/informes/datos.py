"""Datos del informe de conciliación, comunes al PDF y al Excel (así nunca difieren)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from django.utils import timezone

from apps.conciliaciones import servicios
from apps.conciliaciones.models import (
    Conciliacion,
    EstadoConciliacion,
    OrigenMovimiento,
    TipoPartida,
)
from motor.texto import NOMBRE_MES


class InformeNoDisponible(servicios.ErrorConciliacion):
    pass


TIPOS_CRUCE = {
    "cheque": "Nº de cheque",
    "monto_fecha": "Monto y fecha",
    "sugerido": "Sugerido",
    "manual": "Manual",
}


@dataclass(frozen=True)
class FilaPartida:
    fecha: date | None
    comprobante: int | None
    detalle: str  # glosa (concepto del egreso o detalle del ingreso, ej. "G.C")
    referencia: str  # nº de cheque (egresos) o depto (ingresos)
    monto: int
    mes_anterior: bool


@dataclass(frozen=True)
class FilaMovimiento:
    fecha: date
    descripcion: str
    documento: str
    monto_con_signo: int
    mes_anterior: bool


@dataclass(frozen=True)
class FilaCruce:
    partida_tipo: str
    comprobante: int | None
    fecha_libro: date | None
    detalle_libro: str
    fecha_banco: date
    detalle_banco: str
    monto: int
    tipo: str
    confirmado_por: str


@dataclass(frozen=True)
class FilaCartola:
    fecha: date
    descripcion: str
    documento: str
    cargo: int | None
    abono: int | None
    estado: str


@dataclass
class InformeConciliacion:
    comunidad: str
    comunidad_rut: str
    comunidad_direccion: str
    banco: str
    cuenta: str
    periodo_texto: str  # "Mayo 2026"
    periodo_anterior_texto: str
    es_saldo_inicial: bool
    cerrada: bool
    estado_texto: str
    cerrada_por: str
    cerrada_en: datetime | None
    cartola_numero: str
    cartola_desde: date | None
    cartola_hasta: date | None
    resumen: servicios.Resumen
    cheques: list[FilaPartida] = field(default_factory=list)
    depositos: list[FilaPartida] = field(default_factory=list)
    no_contabilizados: list[FilaMovimiento] = field(default_factory=list)
    cruces: list[FilaCruce] = field(default_factory=list)
    cartola: list[FilaCartola] = field(default_factory=list)
    generado_en: datetime = field(default_factory=timezone.localtime)
    generado_por: str = ""

    @property
    def titulo(self) -> str:
        if self.es_saldo_inicial:
            return f"Saldo inicial · {self.periodo_texto}"
        return f"Conciliación bancaria · {self.periodo_texto}"

    @property
    def nombre_archivo(self) -> str:
        base = "".join(ch if ch.isalnum() else "_" for ch in self.comunidad).strip("_")
        partes = self.periodo_texto.split()
        return f"Conciliacion_{base}_{partes[1]}-{_numero_mes(partes[0]):02d}"


def _numero_mes(nombre: str) -> int:
    return next(n for n, m in NOMBRE_MES.items() if m == nombre)


def _nombre_periodo(anio: int, mes: int) -> str:
    return f"{NOMBRE_MES[mes]} {anio}"


def _nombre_usuario(usuario) -> str:
    if usuario is None:
        return ""
    return usuario.get_full_name() or usuario.get_username()


def armar_informe(c: Conciliacion, usuario=None) -> InformeConciliacion:
    if c.estado == EstadoConciliacion.BORRADOR:
        raise InformeNoDisponible("El informe está disponible después de procesar la conciliación.")
    comunidad = c.cuenta.comunidad
    anterior = c.periodo.anterior()
    informe = InformeConciliacion(
        comunidad=comunidad.nombre,
        comunidad_rut=comunidad.rut,
        comunidad_direccion=comunidad.direccion,
        banco=c.cuenta.get_banco_display(),
        cuenta=c.cuenta.numero,
        periodo_texto=_nombre_periodo(c.anio, c.mes),
        periodo_anterior_texto=_nombre_periodo(anterior.anio, anterior.mes),
        es_saldo_inicial=c.estado == EstadoConciliacion.IMPORTADA,
        cerrada=c.estado in (EstadoConciliacion.CERRADA, EstadoConciliacion.IMPORTADA),
        estado_texto=c.get_estado_display(),
        cerrada_por=_nombre_usuario(c.cerrada_por),
        cerrada_en=timezone.localtime(c.cerrada_en) if c.cerrada_en else None,
        cartola_numero=c.cartola_numero,
        cartola_desde=c.cartola_desde,
        cartola_hasta=c.cartola_hasta,
        resumen=servicios.calcular_resumen(c),
        generado_por=_nombre_usuario(usuario),
    )

    pendientes = c.partidas.filter(cruce__isnull=True).order_by("fecha", "comprobante")
    for p in pendientes:
        # en un saldo inicial todo viene "de antes": la marca solo aporta en meses procesados
        anterior_mes = p.origen == "arrastre" and not informe.es_saldo_inicial
        if p.tipo == TipoPartida.EGRESO:
            informe.cheques.append(
                FilaPartida(p.fecha, p.comprobante, p.glosa, p.cheque, p.monto, anterior_mes)
            )
        else:
            informe.depositos.append(
                FilaPartida(p.fecha, p.comprobante, p.glosa, p.depto, p.monto, anterior_mes)
            )

    sin_cruce = (
        c.movimientos.filter(cruce__isnull=True)
        .exclude(origen=OrigenMovimiento.REPETIDO)
        .order_by("fecha", "id")
    )
    informe.no_contabilizados = [
        FilaMovimiento(
            m.fecha,
            m.descripcion,
            m.documento,
            m.monto_con_signo,
            m.origen == OrigenMovimiento.ARRASTRE and not informe.es_saldo_inicial,
        )
        for m in sin_cruce
    ]

    cruces = c.cruces.select_related("partida", "movimiento", "confirmado_por").order_by(
        "movimiento__fecha", "movimiento__id"
    )
    por_movimiento: dict[int, str] = {}
    for x in cruces:
        p, m = x.partida, x.movimiento
        informe.cruces.append(
            FilaCruce(
                partida_tipo=p.get_tipo_display(),
                comprobante=p.comprobante,
                fecha_libro=p.fecha,
                detalle_libro=p.glosa if p.tipo == TipoPartida.EGRESO else f"Depto {p.depto}",
                fecha_banco=m.fecha,
                detalle_banco=m.descripcion,
                monto=p.monto,
                tipo=TIPOS_CRUCE[x.tipo],
                confirmado_por=_nombre_usuario(x.confirmado_por),
            )
        )
        por_movimiento[m.id] = f"Cruzado con {p.get_tipo_display().lower()} #{p.comprobante}"

    de_la_cartola = c.movimientos.filter(
        origen__in=[OrigenMovimiento.PERIODO, OrigenMovimiento.REPETIDO]
    ).order_by("fecha", "id")
    for m in de_la_cartola:
        if m.origen == OrigenMovimiento.REPETIDO:
            estado = "Repetido de la cartola anterior"
        else:
            estado = por_movimiento.get(m.id, "No contabilizado")
        informe.cartola.append(
            FilaCartola(
                m.fecha,
                m.descripcion,
                m.documento,
                m.monto if m.es_cargo else None,
                None if m.es_cargo else m.monto,
                estado,
            )
        )
    return informe
