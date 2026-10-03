from dataclasses import asdict

from rest_framework import serializers

from apps.conciliaciones import servicios
from apps.conciliaciones.models import (
    ArchivoCargado,
    Conciliacion,
    Cruce,
    Evento,
    Movimiento,
    OrigenMovimiento,
    Partida,
    TipoArchivo,
    TipoPartida,
)


def _nombre_usuario(usuario) -> str | None:
    if usuario is None:
        return None
    return usuario.get_full_name() or usuario.get_username()


class PartidaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partida
        fields = [
            "id",
            "tipo",
            "origen",
            "comprobante",
            "fecha",
            "monto",
            "glosa",
            "depto",
            "cheque",
        ]


class MovimientoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movimiento
        fields = [
            "id", "origen", "fecha", "descripcion", "monto", "es_cargo", "documento", "sucursal",
        ]  # fmt: skip


class CruceSerializer(serializers.ModelSerializer):
    partida = PartidaSerializer(read_only=True)
    movimiento = MovimientoSerializer(read_only=True)
    requiere_revision = serializers.BooleanField(read_only=True)
    confirmado_por = serializers.SerializerMethodField()

    class Meta:
        model = Cruce
        fields = [
            "id", "tipo", "nota", "confirmado", "confirmado_por", "confirmado_en",
            "requiere_revision", "partida", "movimiento",
        ]  # fmt: skip

    def get_confirmado_por(self, obj) -> str | None:
        return _nombre_usuario(obj.confirmado_por)


class ArchivoSerializer(serializers.ModelSerializer):
    subido_por = serializers.SerializerMethodField()

    class Meta:
        model = ArchivoCargado
        fields = ["id", "tipo", "nombre_original", "tamano", "sha256", "subido_por", "subido_en"]

    def get_subido_por(self, obj) -> str | None:
        return _nombre_usuario(obj.subido_por)


class EventoSerializer(serializers.ModelSerializer):
    usuario = serializers.SerializerMethodField()

    class Meta:
        model = Evento
        fields = ["id", "accion", "detalle", "usuario", "fecha"]

    def get_usuario(self, obj) -> str | None:
        return _nombre_usuario(obj.usuario)


class ConciliacionSerializer(serializers.ModelSerializer):
    """Listado: datos básicos + resumen de saldos."""

    periodo = serializers.SerializerMethodField()
    resumen = serializers.SerializerMethodField()
    cuenta_nombre = serializers.CharField(source="cuenta.__str__", read_only=True)
    cuenta_numero = serializers.CharField(source="cuenta.numero", read_only=True)
    banco_nombre = serializers.CharField(source="cuenta.get_banco_display", read_only=True)
    comunidad_id = serializers.IntegerField(source="cuenta.comunidad_id", read_only=True)
    comunidad_nombre = serializers.CharField(source="cuenta.comunidad.nombre", read_only=True)

    class Meta:
        model = Conciliacion
        fields = [
            "id", "cuenta", "cuenta_nombre", "cuenta_numero", "banco_nombre", "comunidad_id",
            "comunidad_nombre", "anio", "mes", "periodo", "estado",
            "creada_en", "procesada_en", "cerrada_en", "resumen",
        ]  # fmt: skip
        read_only_fields = fields

    def get_periodo(self, obj) -> str:
        return str(obj.periodo)

    def get_resumen(self, obj) -> dict:
        return asdict(servicios.calcular_resumen(obj))


class ConciliacionDetalleSerializer(ConciliacionSerializer):
    """Detalle: todo lo necesario para la mesa de trabajo y los informes."""

    cheques_pendientes = serializers.SerializerMethodField()
    depositos_pendientes = serializers.SerializerMethodField()
    movimientos_no_contabilizados = serializers.SerializerMethodField()
    movimientos_repetidos = serializers.SerializerMethodField()
    cruces = serializers.SerializerMethodField()
    archivos = ArchivoSerializer(many=True, read_only=True)
    eventos = EventoSerializer(many=True, read_only=True)
    cerrada_por = serializers.SerializerMethodField()

    class Meta(ConciliacionSerializer.Meta):
        fields = ConciliacionSerializer.Meta.fields + [
            "advertencias", "cerrada_por", "cheques_pendientes", "depositos_pendientes",
            "movimientos_no_contabilizados", "movimientos_repetidos", "cruces", "archivos",
            "eventos",
        ]  # fmt: skip
        read_only_fields = fields

    def _pendientes(self, obj, tipo):
        qs = obj.partidas.filter(tipo=tipo, cruce__isnull=True)
        return PartidaSerializer(qs, many=True).data

    def get_cheques_pendientes(self, obj):
        return self._pendientes(obj, TipoPartida.EGRESO)

    def get_depositos_pendientes(self, obj):
        return self._pendientes(obj, TipoPartida.INGRESO)

    def get_movimientos_no_contabilizados(self, obj):
        qs = obj.movimientos.filter(cruce__isnull=True).exclude(origen=OrigenMovimiento.REPETIDO)
        return MovimientoSerializer(qs, many=True).data

    def get_movimientos_repetidos(self, obj):
        qs = obj.movimientos.filter(origen=OrigenMovimiento.REPETIDO)
        return MovimientoSerializer(qs, many=True).data

    def get_cruces(self, obj):
        qs = obj.cruces.select_related("partida", "movimiento", "confirmado_por").order_by(
            "movimiento__fecha", "movimiento__id"
        )
        return CruceSerializer(qs, many=True).data

    def get_cerrada_por(self, obj) -> str | None:
        return _nombre_usuario(obj.cerrada_por)


class CrearConciliacionSerializer(serializers.Serializer):
    cuenta = serializers.IntegerField()
    periodo = serializers.RegexField(r"^\d{4}-(0[1-9]|1[0-2])$", error_messages={
        "invalid": "Formato esperado: AAAA-MM."
    })  # fmt: skip


class SubirArchivoSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(
        choices=[TipoArchivo.INGRESOS, TipoArchivo.EGRESOS, TipoArchivo.CARTOLA]
    )
    archivo = serializers.FileField()


class CruceManualSerializer(serializers.Serializer):
    partida = serializers.IntegerField()
    movimiento = serializers.IntegerField()


class _ChequePendienteSerializer(serializers.Serializer):
    comprobante = serializers.IntegerField(required=False, allow_null=True)
    fecha = serializers.DateField(required=False, allow_null=True)
    monto = serializers.IntegerField(min_value=1)
    glosa = serializers.CharField(required=False, allow_blank=True, default="")
    cheque = serializers.CharField(required=False, allow_blank=True, default="", max_length=40)


class _DepositoPendienteSerializer(serializers.Serializer):
    comprobante = serializers.IntegerField(required=False, allow_null=True)
    fecha = serializers.DateField(required=False, allow_null=True)
    monto = serializers.IntegerField(min_value=1)
    depto = serializers.CharField(required=False, allow_blank=True, default="", max_length=40)
    glosa = serializers.CharField(required=False, allow_blank=True, default="")


class _MovimientoPendienteSerializer(serializers.Serializer):
    fecha = serializers.DateField()
    descripcion = serializers.CharField(required=False, allow_blank=True, default="")
    monto = serializers.IntegerField(help_text="Abono positivo, cargo negativo")

    def validate_monto(self, valor):
        if valor == 0:
            raise serializers.ValidationError("El monto no puede ser 0.")
        return valor


class AperturaManualSerializer(serializers.Serializer):
    periodo = serializers.RegexField(
        r"^\d{4}-(0[1-9]|1[0-2])$", error_messages={"invalid": "Formato esperado: AAAA-MM."}
    )
    saldo_registro = serializers.IntegerField()
    saldo_banco = serializers.IntegerField()
    cheques_pendientes = _ChequePendienteSerializer(many=True, required=False, default=list)
    depositos_pendientes = _DepositoPendienteSerializer(many=True, required=False, default=list)
    movimientos_no_contabilizados = _MovimientoPendienteSerializer(
        many=True, required=False, default=list
    )


class RedondeoSerializer(serializers.Serializer):
    monto = serializers.IntegerField()


class ReabrirSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=500)
