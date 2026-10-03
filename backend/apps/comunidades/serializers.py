from rest_framework import serializers

from apps.comunidades.models import Comunidad, CuentaBancaria


class CuentaBancariaSerializer(serializers.ModelSerializer):
    banco_nombre = serializers.CharField(source="get_banco_display", read_only=True)
    comunidad_nombre = serializers.CharField(source="comunidad.nombre", read_only=True)

    class Meta:
        model = CuentaBancaria
        fields = [
            "id",
            "comunidad",
            "comunidad_nombre",
            "banco",
            "banco_nombre",
            "numero",
            "activa",
        ]


class ComunidadSerializer(serializers.ModelSerializer):
    cuentas = CuentaBancariaSerializer(many=True, read_only=True)

    class Meta:
        model = Comunidad
        fields = ["id", "nombre", "rut", "direccion", "activa", "cuentas"]
