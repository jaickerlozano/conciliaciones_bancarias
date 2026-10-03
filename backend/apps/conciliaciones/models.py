"""Persistencia de las conciliaciones.

Una `Conciliacion` por cuenta y mes. Sus partidas (libro) y movimientos (banco) se guardan
completos; lo que no tiene `Cruce` son los pendientes. Así, los pendientes de un mes cerrado
son la apertura del mes siguiente, sin copiar listas a mano.
"""

from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.comunidades.models import CuentaBancaria
from motor.dominio import Periodo


class EstadoConciliacion(models.TextChoices):
    IMPORTADA = "importada", "Saldo inicial importado"
    BORRADOR = "borrador", "Borrador"
    PROCESADA = "procesada", "Procesada"
    CERRADA = "cerrada", "Cerrada"


class Conciliacion(models.Model):
    cuenta = models.ForeignKey(
        CuentaBancaria, on_delete=models.PROTECT, related_name="conciliaciones"
    )
    anio = models.PositiveSmallIntegerField("año")
    mes = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    estado = models.CharField(
        max_length=12, choices=EstadoConciliacion.choices, default=EstadoConciliacion.BORRADOR
    )
    saldo_anterior = models.BigIntegerField(default=0)
    total_ingresos = models.BigIntegerField(default=0)
    total_egresos = models.BigIntegerField(default=0)
    redondeo = models.BigIntegerField(default=0)
    saldo_banco = models.BigIntegerField(null=True, blank=True)
    advertencias = models.JSONField(default=list, blank=True)

    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    procesada_en = models.DateTimeField(null=True, blank=True)
    cerrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    cerrada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["cuenta", "-anio", "-mes"]
        verbose_name = "conciliación"
        verbose_name_plural = "conciliaciones"
        constraints = [
            models.UniqueConstraint(
                fields=["cuenta", "anio", "mes"], name="una_conciliacion_por_cuenta_y_mes"
            )
        ]

    def __str__(self) -> str:
        return f"{self.cuenta} — {self.periodo}"

    @property
    def periodo(self) -> Periodo:
        return Periodo(self.anio, self.mes)

    @property
    def saldo_registro(self) -> int:
        return self.saldo_anterior + self.total_ingresos - self.total_egresos + self.redondeo

    @property
    def editable(self) -> bool:
        return self.estado in (EstadoConciliacion.BORRADOR, EstadoConciliacion.PROCESADA)


class TipoPartida(models.TextChoices):
    INGRESO = "INGRESO", "Ingreso"
    EGRESO = "EGRESO", "Egreso"


class OrigenPartida(models.TextChoices):
    PERIODO = "periodo", "Del período"
    ARRASTRE = "arrastre", "Pendiente de meses anteriores"


class OrigenMovimiento(models.TextChoices):
    PERIODO = "periodo", "De la cartola del período"
    ARRASTRE = "arrastre", "No contabilizado de meses anteriores"
    REPETIDO = "repetido", "Repetido de la cartola anterior (descartado)"


class Partida(models.Model):
    conciliacion = models.ForeignKey(
        Conciliacion, on_delete=models.CASCADE, related_name="partidas"
    )
    tipo = models.CharField(max_length=7, choices=TipoPartida.choices)
    origen = models.CharField(max_length=8, choices=OrigenPartida.choices)
    comprobante = models.IntegerField(null=True, blank=True)
    fecha = models.DateField(null=True, blank=True)
    monto = models.BigIntegerField()
    glosa = models.TextField(blank=True)
    depto = models.CharField(max_length=40, blank=True)
    cheque = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["tipo", "fecha", "comprobante"]

    def __str__(self) -> str:
        return f"{self.tipo} #{self.comprobante} ${self.monto:,}"


class Movimiento(models.Model):
    conciliacion = models.ForeignKey(
        Conciliacion, on_delete=models.CASCADE, related_name="movimientos"
    )
    origen = models.CharField(max_length=8, choices=OrigenMovimiento.choices)
    fecha = models.DateField()
    descripcion = models.CharField(max_length=255, blank=True)
    monto = models.BigIntegerField()  # siempre positivo
    es_cargo = models.BooleanField()
    documento = models.CharField(max_length=40, blank=True)
    sucursal = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ["fecha", "id"]

    def __str__(self) -> str:
        return f"{self.fecha} {'cargo' if self.es_cargo else 'abono'} ${self.monto:,}"

    @property
    def monto_con_signo(self) -> int:
        return -self.monto if self.es_cargo else self.monto


class TipoCruce(models.TextChoices):
    CHEQUE = "cheque", "Nº de cheque"
    MONTO_FECHA = "monto_fecha", "Monto y fecha"
    SUGERIDO = "sugerido", "Sugerido (revisar)"
    MANUAL = "manual", "Manual"


class Cruce(models.Model):
    conciliacion = models.ForeignKey(Conciliacion, on_delete=models.CASCADE, related_name="cruces")
    partida = models.OneToOneField(Partida, on_delete=models.CASCADE, related_name="cruce")
    movimiento = models.OneToOneField(Movimiento, on_delete=models.CASCADE, related_name="cruce")
    tipo = models.CharField(max_length=12, choices=TipoCruce.choices)
    nota = models.CharField(max_length=255, blank=True)
    confirmado = models.BooleanField(default=False)
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    confirmado_en = models.DateTimeField(null=True, blank=True)

    @property
    def requiere_revision(self) -> bool:
        return not self.confirmado and (self.tipo == TipoCruce.SUGERIDO or bool(self.nota))


class TipoArchivo(models.TextChoices):
    INGRESOS = "ingresos", "Planilla de ingresos"
    EGRESOS = "egresos", "Planilla de egresos"
    CARTOLA = "cartola", "Cartola bancaria"
    APERTURA = "apertura", "Planilla de conciliación (saldo inicial)"


def _ruta_archivo(instancia: ArchivoCargado, nombre: str) -> str:
    c = instancia.conciliacion
    return f"cuentas/{c.cuenta_id}/{c.anio}-{c.mes:02d}/{instancia.tipo}/{nombre}"


class ArchivoCargado(models.Model):
    conciliacion = models.ForeignKey(
        Conciliacion, on_delete=models.CASCADE, related_name="archivos"
    )
    tipo = models.CharField(max_length=10, choices=TipoArchivo.choices)
    archivo = models.FileField(upload_to=_ruta_archivo, max_length=500)
    nombre_original = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64)
    tamano = models.PositiveIntegerField("tamaño (bytes)")
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    subido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "archivo cargado"
        verbose_name_plural = "archivos cargados"
        constraints = [
            models.UniqueConstraint(
                fields=["conciliacion", "tipo"], name="un_archivo_por_tipo_y_conciliacion"
            )
        ]


class AccionEvento(models.TextChoices):
    IMPORTADA = "importada", "Saldo inicial importado"
    CREADA = "creada", "Conciliación creada"
    ARCHIVO = "archivo", "Archivo cargado"
    PROCESADA = "procesada", "Procesada"
    CRUCE_CONFIRMADO = "cruce_confirmado", "Cruce confirmado"
    CRUCE_DESHECHO = "cruce_deshecho", "Cruce deshecho"
    CRUCE_MANUAL = "cruce_manual", "Cruce manual"
    REDONDEO = "redondeo", "Redondeo ajustado"
    CERRADA = "cerrada", "Cerrada"
    REABIERTA = "reabierta", "Reabierta"


class Evento(models.Model):
    """Bitácora de auditoría: quién hizo qué y cuándo."""

    conciliacion = models.ForeignKey(Conciliacion, on_delete=models.CASCADE, related_name="eventos")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    accion = models.CharField(max_length=20, choices=AccionEvento.choices)
    detalle = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-id"]
