"""Casos de uso de las conciliaciones. Las vistas solo validan la entrada HTTP y llaman aquí.

Flujo mensual:
    importar_apertura (una vez por cuenta) -> crear_conciliacion -> guardar_archivo (x3)
    -> procesar -> confirmar/deshacer/cruzar_manual -> cerrar -> (mes siguiente)
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import BigIntegerField, Case, F, Q, Sum, When
from django.utils import timezone

from apps.comunidades.models import CuentaBancaria
from apps.conciliaciones.models import (
    AccionEvento,
    ArchivoCargado,
    Conciliacion,
    Cruce,
    EstadoConciliacion,
    Evento,
    Movimiento,
    OrigenMovimiento,
    OrigenPartida,
    Partida,
    TipoArchivo,
    TipoCruce,
    TipoPartida,
)
from motor import dominio
from motor.conciliacion import conciliar
from motor.parsers.cartolas import leer_cartola
from motor.parsers.conciliacion_cliente import leer_conciliacion_cliente
from motor.parsers.libros import LibroContable, leer_libro
from motor.texto import NOMBRE_MES, fmt_clp, normalizar

# Las planillas son acumuladas (años de historia) y solo se usa el bloque del mes: el límite
# operativo es por mes; el del archivo completo es solo un tope de seguridad.
MAX_PARTIDAS_PERIODO = 5_000
MAX_PARTIDAS_PLANILLA = 200_000
MAX_REDONDEO = 100  # pesos: el redondeo solo absorbe decimales (cuotas en UF), no diferencias

EXTENSIONES = {
    TipoArchivo.INGRESOS: (".xlsx", ".xlsm"),
    TipoArchivo.EGRESOS: (".xlsx", ".xlsm"),
    TipoArchivo.CARTOLA: (".pdf", ".xlsx", ".xls", ".csv"),
    TipoArchivo.APERTURA: (".xlsx", ".xlsm"),
}


class ErrorConciliacion(Exception):
    """Regla de negocio incumplida. El mensaje se muestra tal cual al usuario."""


# --------------------------------------------------------------------------- consultas


def anterior(c: Conciliacion) -> Conciliacion | None:
    p = c.periodo.anterior()
    return Conciliacion.objects.filter(cuenta=c.cuenta, anio=p.anio, mes=p.mes).first()


def siguiente(c: Conciliacion) -> Conciliacion | None:
    p = c.periodo.siguiente()
    return Conciliacion.objects.filter(cuenta=c.cuenta, anio=p.anio, mes=p.mes).first()


@dataclass(frozen=True)
class Resumen:
    saldo_anterior: int
    total_ingresos: int
    total_egresos: int
    redondeo: int
    saldo_registro: int
    total_cheques_pendientes: int
    total_depositos_pendientes: int
    total_no_contabilizados: int
    saldo_conciliacion: int
    saldo_banco: int | None
    diferencia: int | None
    cruces_por_revisar: int


def calcular_resumen(c: Conciliacion) -> Resumen:
    pendientes = c.partidas.filter(cruce__isnull=True).aggregate(
        cheques=Sum("monto", filter=Q(tipo=TipoPartida.EGRESO), default=0),
        depositos=Sum("monto", filter=Q(tipo=TipoPartida.INGRESO), default=0),
    )
    no_contabilizados = (
        c.movimientos.filter(cruce__isnull=True)
        .exclude(origen=OrigenMovimiento.REPETIDO)
        .aggregate(
            total=Sum(
                Case(
                    When(es_cargo=True, then=-F("monto")),
                    default=F("monto"),
                    output_field=BigIntegerField(),
                ),
                default=0,
            )
        )["total"]
    )
    por_revisar = (
        c.cruces.filter(confirmado=False).filter(Q(tipo=TipoCruce.SUGERIDO) | ~Q(nota="")).count()
    )
    conciliacion = (
        c.saldo_registro + pendientes["cheques"] - pendientes["depositos"] + no_contabilizados
    )
    return Resumen(
        saldo_anterior=c.saldo_anterior,
        total_ingresos=c.total_ingresos,
        total_egresos=c.total_egresos,
        redondeo=c.redondeo,
        saldo_registro=c.saldo_registro,
        total_cheques_pendientes=pendientes["cheques"],
        total_depositos_pendientes=pendientes["depositos"],
        total_no_contabilizados=no_contabilizados,
        saldo_conciliacion=conciliacion,
        saldo_banco=c.saldo_banco,
        diferencia=None if c.saldo_banco is None else c.saldo_banco - conciliacion,
        cruces_por_revisar=por_revisar,
    )


# --------------------------------------------------------------------------- archivos


def validar_archivo(archivo: UploadedFile, tipo: str) -> None:
    extension = Path(archivo.name).suffix.lower()
    permitidas = EXTENSIONES[TipoArchivo(tipo)]
    if extension not in permitidas:
        raise ErrorConciliacion(
            f"'{archivo.name}' no es un archivo válido para {TipoArchivo(tipo).label.lower()}. "
            f"Formatos aceptados: {', '.join(permitidas)}."
        )
    limite = (
        settings.TAMANO_MAXIMO_APERTURA
        if tipo == TipoArchivo.APERTURA
        else settings.TAMANO_MAXIMO_ARCHIVO
    )
    if archivo.size > limite:
        maximo = limite // (1024 * 1024)
        raise ErrorConciliacion(f"'{archivo.name}' supera el máximo de {maximo} MB.")


def _sha256(archivo: UploadedFile) -> str:
    h = hashlib.sha256()
    for bloque in archivo.chunks():
        h.update(bloque)
    archivo.seek(0)
    return h.hexdigest()


def _guardar(c: Conciliacion, tipo: str, archivo: UploadedFile, usuario) -> ArchivoCargado:
    validar_archivo(archivo, tipo)
    for previo in c.archivos.filter(tipo=tipo):
        previo.archivo.delete(save=False)
        previo.delete()
    return ArchivoCargado.objects.create(
        conciliacion=c,
        tipo=tipo,
        archivo=archivo,
        nombre_original=archivo.name,
        sha256=_sha256(archivo),
        tamano=archivo.size,
        subido_por=usuario,
    )


def _evento(c: Conciliacion, usuario, accion: str, detalle: str = "") -> None:
    Evento.objects.create(conciliacion=c, usuario=usuario, accion=accion, detalle=detalle)


# --------------------------------------------------------------------------- conversión


def _a_partida_libro(p: Partida) -> dominio.PartidaLibro:
    return dominio.PartidaLibro(
        tipo=dominio.TipoPartida(p.tipo),
        comprobante=p.comprobante,
        fecha=p.fecha,
        monto=p.monto,
        glosa=p.glosa,
        depto=p.depto,
        cheque=p.cheque,
    )


def _a_movimiento_bancario(m: Movimiento) -> dominio.MovimientoBancario:
    return dominio.MovimientoBancario(
        fecha=m.fecha,
        descripcion=m.descripcion,
        monto=m.monto,
        es_cargo=m.es_cargo,
        documento=m.documento,
        sucursal=m.sucursal,
    )


def _nueva_partida(c: Conciliacion, p: dominio.PartidaLibro, origen: str) -> Partida:
    return Partida(
        conciliacion=c,
        tipo=p.tipo.value,
        origen=origen,
        comprobante=p.comprobante,
        fecha=p.fecha,
        monto=p.monto,
        glosa=p.glosa,
        depto=p.depto[:40],
        cheque=p.cheque[:40],
    )


def _nuevo_movimiento(c: Conciliacion, m: dominio.MovimientoBancario, origen: str) -> Movimiento:
    return Movimiento(
        conciliacion=c,
        origen=origen,
        fecha=m.fecha,
        descripcion=m.descripcion[:255],
        monto=m.monto,
        es_cargo=m.es_cargo,
        documento=m.documento[:40],
        sucursal=m.sucursal[:60],
    )


def apertura_desde(previa: Conciliacion) -> dominio.EstadoApertura:
    """Los pendientes de la conciliación anterior son la apertura de la siguiente."""
    partidas = previa.partidas.filter(cruce__isnull=True)
    sin_cruce = previa.movimientos.filter(cruce__isnull=True).exclude(
        origen=OrigenMovimiento.REPETIDO
    )
    de_la_cartola = previa.movimientos.filter(
        origen__in=[OrigenMovimiento.PERIODO, OrigenMovimiento.REPETIDO]
    )
    return dominio.EstadoApertura(
        saldo_registro=previa.saldo_registro,
        saldo_banco=previa.saldo_banco,
        cheques_pendientes=[_a_partida_libro(p) for p in partidas.filter(tipo=TipoPartida.EGRESO)],
        depositos_pendientes=[
            _a_partida_libro(p) for p in partidas.filter(tipo=TipoPartida.INGRESO)
        ],
        movimientos_no_contabilizados=[_a_movimiento_bancario(m) for m in sin_cruce],
        movimientos_cartola_anterior=[_a_movimiento_bancario(m) for m in de_la_cartola],
    )


# --------------------------------------------------------------------------- casos de uso


def _preparar_apertura(cuenta: CuentaBancaria, periodo: dominio.Periodo, usuario) -> Conciliacion:
    """El saldo inicial solo se carga al empezar a usar el sistema con una cuenta (reemplaza
    una carga anterior si aún no hay meses conciliados en el sistema)."""
    existentes = cuenta.conciliaciones.all()
    if existentes.exclude(estado=EstadoConciliacion.IMPORTADA).exists():
        raise ErrorConciliacion(
            "Esta cuenta ya tiene conciliaciones hechas en el sistema; el saldo inicial solo "
            "se carga al comenzar."
        )
    for previa in existentes:
        eliminar_sin_validar(previa)
    return Conciliacion.objects.create(
        cuenta=cuenta,
        anio=periodo.anio,
        mes=periodo.mes,
        estado=EstadoConciliacion.IMPORTADA,
        creada_por=usuario,
    )


def _cargar_saldo_inicial(
    c: Conciliacion,
    saldo_registro: int,
    saldo_banco: int,
    cheques: list[dominio.PartidaLibro],
    depositos: list[dominio.PartidaLibro],
    no_contabilizados: list[dominio.MovimientoBancario],
) -> Resumen:
    c.saldo_anterior = saldo_registro  # sin ingresos/egresos: registro = saldo inicial
    c.saldo_banco = saldo_banco
    Partida.objects.bulk_create(
        _nueva_partida(c, p, OrigenPartida.ARRASTRE) for p in cheques + depositos
    )
    Movimiento.objects.bulk_create(
        _nuevo_movimiento(c, m, OrigenMovimiento.ARRASTRE) for m in no_contabilizados
    )
    c.save()
    return calcular_resumen(c)


@transaction.atomic
def importar_apertura(
    cuenta: CuentaBancaria,
    archivo: UploadedFile,
    hoja: str,
    periodo: dominio.Periodo,
    usuario,
) -> Conciliacion:
    """Saldo inicial desde la última hoja de conciliación hecha a mano por el cliente."""
    c = _preparar_apertura(cuenta, periodo, usuario)
    registro = _guardar(c, TipoArchivo.APERTURA, archivo, usuario)
    datos = leer_conciliacion_cliente(registro.archivo.path, hoja)
    if datos.saldo_registro is None or datos.saldo_banco is None:
        raise ErrorConciliacion(
            f"La hoja '{hoja}' no tiene 'Saldo según registro' o 'Saldo según banco'. "
            "¿Es una hoja de conciliación mensual?"
        )
    resumen = _cargar_saldo_inicial(
        c, datos.saldo_registro, datos.saldo_banco, datos.cheques_pendientes,
        datos.depositos_pendientes, datos.movimientos_no_contabilizados,
    )  # fmt: skip
    if resumen.diferencia:
        c.advertencias = [
            f"La hoja importada no cuadra: diferencia de {fmt_clp(resumen.diferencia)}."
        ]
        c.save(update_fields=["advertencias"])
    _evento(c, usuario, AccionEvento.IMPORTADA, f"Hoja '{hoja}' de {archivo.name}")
    return c


@transaction.atomic
def apertura_manual(
    cuenta: CuentaBancaria,
    periodo: dominio.Periodo,
    saldo_registro: int,
    saldo_banco: int,
    cheques: list[dominio.PartidaLibro],
    depositos: list[dominio.PartidaLibro],
    no_contabilizados: list[dominio.MovimientoBancario],
    usuario,
) -> Conciliacion:
    """Saldo inicial ingresado a mano: saldos del cierre del mes `periodo` y sus pendientes.
    Debe cuadrar exactamente (si no, no se guarda nada)."""
    c = _preparar_apertura(cuenta, periodo, usuario)
    resumen = _cargar_saldo_inicial(
        c, saldo_registro, saldo_banco, cheques, depositos, no_contabilizados
    )
    if resumen.diferencia:
        raise ErrorConciliacion(
            f"El saldo inicial no cuadra: saldo banco {fmt_clp(saldo_banco)} vs saldo según "
            f"conciliación {fmt_clp(resumen.saldo_conciliacion)} (diferencia "
            f"{fmt_clp(resumen.diferencia)}). Revise los saldos y los pendientes."
        )
    detalle = (
        f"Ingreso manual: {len(cheques)} cheques, {len(depositos)} depósitos y "
        f"{len(no_contabilizados)} movimientos pendientes."
    )
    _evento(c, usuario, AccionEvento.IMPORTADA, detalle)
    return c


def crear_conciliacion(cuenta: CuentaBancaria, periodo: dominio.Periodo, usuario) -> Conciliacion:
    if cuenta.conciliaciones.filter(anio=periodo.anio, mes=periodo.mes).exists():
        raise ErrorConciliacion(f"Ya existe la conciliación de {periodo} para esta cuenta.")
    p = periodo.anterior()
    previa = cuenta.conciliaciones.filter(anio=p.anio, mes=p.mes).first()
    if previa is None:
        raise ErrorConciliacion(
            f"No existe la conciliación de {p}. Si es la primera vez que usa el sistema con "
            "esta cuenta, importe primero el saldo inicial desde la planilla de conciliación."
        )
    if previa.estado not in (EstadoConciliacion.CERRADA, EstadoConciliacion.IMPORTADA):
        raise ErrorConciliacion(
            f"Debe cerrar la conciliación de {p} antes de crear la de {periodo}."
        )
    c = Conciliacion.objects.create(
        cuenta=cuenta, anio=periodo.anio, mes=periodo.mes, creada_por=usuario
    )
    _evento(c, usuario, AccionEvento.CREADA)
    return c


def _exigir_editable(c: Conciliacion) -> None:
    if not c.editable:
        raise ErrorConciliacion(
            f"La conciliación de {c.periodo} está {c.get_estado_display().lower()}; "
            "no se puede modificar."
        )


def _limpiar_resultados(c: Conciliacion) -> None:
    c.cruces.all().delete()
    c.partidas.all().delete()
    c.movimientos.all().delete()
    c.saldo_anterior = c.total_ingresos = c.total_egresos = c.redondeo = 0
    c.saldo_banco = None
    c.cartola_numero = ""
    c.cartola_desde = c.cartola_hasta = None
    c.advertencias = []
    c.procesada_en = None
    c.estado = EstadoConciliacion.BORRADOR


@transaction.atomic
def guardar_archivo(c: Conciliacion, tipo: str, archivo: UploadedFile, usuario) -> ArchivoCargado:
    _exigir_editable(c)
    if tipo == TipoArchivo.APERTURA:
        raise ErrorConciliacion("La planilla de saldo inicial se importa desde la cuenta.")
    registro = _guardar(c, tipo, archivo, usuario)
    if c.estado == EstadoConciliacion.PROCESADA:
        _limpiar_resultados(c)  # los resultados ya no corresponden a los archivos
        c.save()
    _evento(c, usuario, AccionEvento.ARCHIVO, f"{TipoArchivo(tipo).label}: {archivo.name}")
    return registro


def validar_tamano_libro(libro: LibroContable, periodo: dominio.Periodo, nombre: str) -> None:
    """Rechaza un mes desmesurado o un archivo absurdo, sin castigar los años de historia."""
    del_mes = len(libro.partidas(periodo))
    if del_mes > MAX_PARTIDAS_PERIODO:
        raise ErrorConciliacion(
            f"El bloque de {_nombre_periodo(periodo)} de la planilla de {nombre} tiene "
            f"{_miles(del_mes)} partidas; el máximo por mes es {_miles(MAX_PARTIDAS_PERIODO)}. "
            '¿Falta una fila "CIERRE MES" que separe los meses?'
        )
    total = sum(len(ps) for ps in libro.bloques.values())
    if total > MAX_PARTIDAS_PLANILLA:
        raise ErrorConciliacion(
            f"La planilla de {nombre} tiene {_miles(total)} partidas en total; el máximo es "
            f"{_miles(MAX_PARTIDAS_PLANILLA)}. Archive los años antiguos en otro archivo."
        )


def _miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _nombre_periodo(periodo: dominio.Periodo) -> str:
    return f"{NOMBRE_MES[periodo.mes]} {periodo.anio}"


def _solo_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto).lstrip("0")


def _validar_cartola_de_la_cuenta(cuenta: CuentaBancaria, cartola: dominio.Cartola) -> None:
    if normalizar(cartola.banco) not in normalizar(cuenta.get_banco_display()):
        raise ErrorConciliacion(
            f"La cartola es de {cartola.banco}, pero la cuenta es de {cuenta.get_banco_display()}."
        )
    de_cartola, de_cuenta = _solo_digitos(cartola.cuenta), _solo_digitos(cuenta.numero)
    if (
        de_cartola
        and de_cuenta
        and not (de_cartola.endswith(de_cuenta) or de_cuenta.endswith(de_cartola))
    ):
        raise ErrorConciliacion(
            f"La cartola es de la cuenta {cartola.cuenta}, pero se está conciliando la cuenta "
            f"{cuenta.numero}."
        )


@transaction.atomic
def procesar(c: Conciliacion, usuario) -> Conciliacion:
    _exigir_editable(c)
    archivos = {a.tipo: a for a in c.archivos.all()}
    faltan = [
        TipoArchivo(t).label.lower()
        for t in (TipoArchivo.INGRESOS, TipoArchivo.EGRESOS, TipoArchivo.CARTOLA)
        if t not in archivos
    ]
    if faltan:
        raise ErrorConciliacion(f"Falta cargar: {', '.join(faltan)}.")
    previa = anterior(c)
    if previa is None or previa.estado not in (
        EstadoConciliacion.CERRADA,
        EstadoConciliacion.IMPORTADA,
    ):
        raise ErrorConciliacion(f"La conciliación de {c.periodo.anterior()} no está cerrada.")

    periodo = c.periodo
    ingresos = leer_libro(archivos[TipoArchivo.INGRESOS].archivo.path, dominio.TipoPartida.INGRESO)
    egresos = leer_libro(archivos[TipoArchivo.EGRESOS].archivo.path, dominio.TipoPartida.EGRESO)
    for libro, nombre in ((ingresos, "ingresos"), (egresos, "egresos")):
        validar_tamano_libro(libro, c.periodo, nombre)
    cartola = leer_cartola(archivos[TipoArchivo.CARTOLA].archivo.path)
    _validar_cartola_de_la_cuenta(c.cuenta, cartola)

    advertencias: list[str] = []
    for libro, nombre in ((ingresos, "ingresos"), (egresos, "egresos")):
        if not libro.partidas(periodo):
            advertencias.append(f"La planilla de {nombre} no tiene partidas para {periodo}.")
        advertencias += [f"Planilla de {nombre}: {a}" for a in libro.advertencias_de(periodo)]

    r = conciliar(
        periodo, apertura_desde(previa), ingresos.partidas(periodo), egresos.partidas(periodo),
        cartola,
    )  # fmt: skip

    _limpiar_resultados(c)
    _persistir_resultado(c, r)
    c.saldo_anterior = r.saldo_anterior
    c.total_ingresos = r.total_ingresos
    c.total_egresos = r.total_egresos
    c.saldo_banco = r.saldo_banco
    c.cartola_numero = cartola.numero[:20]
    c.cartola_desde = cartola.desde
    c.cartola_hasta = cartola.hasta
    c.advertencias = r.advertencias + advertencias
    c.estado = EstadoConciliacion.PROCESADA
    c.procesada_en = timezone.now()
    c.save()
    por_revisar = sum(x.requiere_revision for x in r.cruces)
    detalle = f"Diferencia {fmt_clp(r.diferencia)}; {por_revisar} cruces por revisar."
    _evento(c, usuario, AccionEvento.PROCESADA, detalle)
    return c


def _persistir_resultado(c: Conciliacion, r: dominio.ResultadoConciliacion) -> None:
    """Guarda todas las partidas y movimientos (cruzados o no) y los cruces."""
    partidas: dict[int, Partida] = {}
    for p in [x.partida for x in r.cruces] + r.cheques_pendientes + r.depositos_pendientes:
        partidas[id(p)] = _nueva_partida(c, p, p.origen.value)
    movimientos: dict[int, Movimiento] = {}
    for m in [x.movimiento for x in r.cruces] + r.movimientos_no_contabilizados:
        movimientos[id(m)] = _nuevo_movimiento(c, m, m.origen.value)
    for m in r.movimientos_descartados:
        movimientos[id(m)] = _nuevo_movimiento(c, m, OrigenMovimiento.REPETIDO)

    Partida.objects.bulk_create(partidas.values())
    Movimiento.objects.bulk_create(movimientos.values())
    Cruce.objects.bulk_create(
        Cruce(
            conciliacion=c,
            partida=partidas[id(x.partida)],
            movimiento=movimientos[id(x.movimiento)],
            tipo=x.tipo.value,
            nota=x.nota[:255],
        )
        for x in r.cruces
    )


def confirmar_cruce(cruce: Cruce, usuario) -> Cruce:
    _exigir_editable(cruce.conciliacion)
    cruce.confirmado = True
    cruce.confirmado_por = usuario
    cruce.confirmado_en = timezone.now()
    cruce.save()
    _evento(
        cruce.conciliacion, usuario, AccionEvento.CRUCE_CONFIRMADO,
        f"Comprobante {cruce.partida.comprobante} ↔ {cruce.movimiento.fecha:%d/%m} "
        f"{fmt_clp(cruce.movimiento.monto)}",
    )  # fmt: skip
    return cruce


@transaction.atomic
def confirmar_todos(c: Conciliacion, usuario) -> int:
    """Confirma todos los cruces por revisar. Devuelve cuántos confirmó."""
    _exigir_editable(c)
    pendientes = [
        x for x in c.cruces.select_related("partida", "movimiento") if x.requiere_revision
    ]
    for cruce in pendientes:
        confirmar_cruce(cruce, usuario)
    return len(pendientes)


def deshacer_cruce(cruce: Cruce, usuario) -> None:
    c = cruce.conciliacion
    _exigir_editable(c)
    detalle = (
        f"Comprobante {cruce.partida.comprobante} ↔ {cruce.movimiento.fecha:%d/%m} "
        f"{fmt_clp(cruce.movimiento.monto)}"
    )
    cruce.delete()
    _evento(c, usuario, AccionEvento.CRUCE_DESHECHO, detalle)


@transaction.atomic
def cruzar_manual(c: Conciliacion, partida: Partida, movimiento: Movimiento, usuario) -> Cruce:
    _exigir_editable(c)
    if partida.conciliacion_id != c.id or movimiento.conciliacion_id != c.id:
        raise ErrorConciliacion("La partida y el movimiento deben ser de esta conciliación.")
    if hasattr(partida, "cruce") or hasattr(movimiento, "cruce"):
        raise ErrorConciliacion("La partida o el movimiento ya están cruzados; deshaga ese cruce.")
    if movimiento.origen == OrigenMovimiento.REPETIDO:
        raise ErrorConciliacion("Ese movimiento está repetido de la cartola anterior.")
    if (partida.tipo == TipoPartida.EGRESO) != movimiento.es_cargo:
        raise ErrorConciliacion(
            "Un egreso solo se cruza con un cargo, y un ingreso solo con un abono."
        )
    if partida.monto != movimiento.monto:
        raise ErrorConciliacion(
            f"Los montos no coinciden: libro {fmt_clp(partida.monto)}, "
            f"banco {fmt_clp(movimiento.monto)}."
        )
    cruce = Cruce.objects.create(
        conciliacion=c,
        partida=partida,
        movimiento=movimiento,
        tipo=TipoCruce.MANUAL,
        confirmado=True,
        confirmado_por=usuario,
        confirmado_en=timezone.now(),
    )
    _evento(
        c, usuario, AccionEvento.CRUCE_MANUAL,
        f"Comprobante {partida.comprobante} ↔ {movimiento.fecha:%d/%m} {fmt_clp(movimiento.monto)}",
    )  # fmt: skip
    return cruce


def ajustar_redondeo(c: Conciliacion, monto: int, usuario) -> Conciliacion:
    if c.estado != EstadoConciliacion.PROCESADA:
        raise ErrorConciliacion("El redondeo se ajusta en una conciliación procesada.")
    if abs(monto) > MAX_REDONDEO:
        raise ErrorConciliacion(
            f"El redondeo no puede superar {fmt_clp(MAX_REDONDEO)}: solo sirve para absorber "
            "decimales. Una diferencia mayor hay que buscarla en los cruces."
        )
    valor_anterior = c.redondeo
    c.redondeo = monto
    c.save(update_fields=["redondeo"])
    _evento(c, usuario, AccionEvento.REDONDEO, f"{fmt_clp(valor_anterior)} → {fmt_clp(monto)}")
    return c


def cerrar(c: Conciliacion, usuario) -> Conciliacion:
    if c.estado != EstadoConciliacion.PROCESADA:
        raise ErrorConciliacion("Solo se puede cerrar una conciliación procesada.")
    resumen = calcular_resumen(c)
    if resumen.diferencia != 0:
        raise ErrorConciliacion(
            f"No se puede cerrar: hay una diferencia de {fmt_clp(resumen.diferencia or 0)}."
        )
    if resumen.cruces_por_revisar:
        raise ErrorConciliacion(
            f"No se puede cerrar: quedan {resumen.cruces_por_revisar} cruces por revisar."
        )
    c.estado = EstadoConciliacion.CERRADA
    c.cerrada_por = usuario
    c.cerrada_en = timezone.now()
    c.save()
    _evento(c, usuario, AccionEvento.CERRADA)
    return c


def reabrir(c: Conciliacion, usuario, motivo: str) -> Conciliacion:
    if c.estado != EstadoConciliacion.CERRADA:
        raise ErrorConciliacion("Solo se puede reabrir una conciliación cerrada.")
    if not motivo.strip():
        raise ErrorConciliacion("Indique el motivo para reabrir la conciliación.")
    sig = siguiente(c)
    if sig is not None:
        raise ErrorConciliacion(
            f"Existe la conciliación de {sig.periodo}, que depende de esta. Elimínela antes."
        )
    c.estado = EstadoConciliacion.PROCESADA
    c.cerrada_por = None
    c.cerrada_en = None
    c.save()
    _evento(c, usuario, AccionEvento.REABIERTA, motivo.strip())
    return c


def eliminar_sin_validar(c: Conciliacion) -> None:
    """Borra la conciliación y sus archivos sin aplicar reglas (uso interno y comandos)."""
    for a in c.archivos.all():
        a.archivo.delete(save=False)
    c.delete()


@transaction.atomic
def eliminar(c: Conciliacion) -> None:
    if c.estado == EstadoConciliacion.CERRADA:
        raise ErrorConciliacion("No se puede eliminar una conciliación cerrada; reábrala antes.")
    sig = siguiente(c)
    if sig is not None:
        raise ErrorConciliacion(
            f"Existe la conciliación de {sig.periodo}, que depende de esta. Elimínela antes."
        )
    eliminar_sin_validar(c)
