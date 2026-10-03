from django.db import models


class Banco(models.TextChoices):
    SANTANDER = "santander", "Santander"
    BCI = "bci", "BCI"
    CHILE = "chile", "Banco de Chile"
    ESTADO = "estado", "BancoEstado"
    ITAU = "itau", "Itaú"
    SCOTIABANK = "scotiabank", "Scotiabank"
    SECURITY = "security", "Security"
    OTRO = "otro", "Otro"


class Comunidad(models.Model):
    nombre = models.CharField(max_length=200, unique=True)
    rut = models.CharField("RUT", max_length=12, blank=True)
    direccion = models.CharField("dirección", max_length=255, blank=True)
    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name_plural = "comunidades"

    def __str__(self) -> str:
        return self.nombre


class CuentaBancaria(models.Model):
    comunidad = models.ForeignKey(Comunidad, on_delete=models.PROTECT, related_name="cuentas")
    banco = models.CharField(max_length=20, choices=Banco.choices)
    numero = models.CharField("número de cuenta", max_length=40)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["comunidad__nombre", "banco"]
        verbose_name = "cuenta bancaria"
        verbose_name_plural = "cuentas bancarias"
        constraints = [
            models.UniqueConstraint(fields=["banco", "numero"], name="cuenta_unica_por_banco")
        ]

    def __str__(self) -> str:
        return f"{self.comunidad} — {self.get_banco_display()} {self.numero}"
