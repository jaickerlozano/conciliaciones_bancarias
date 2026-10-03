from django.contrib import admin

from apps.comunidades.models import Comunidad, CuentaBancaria


class CuentaBancariaInline(admin.TabularInline):
    model = CuentaBancaria
    extra = 0


@admin.register(Comunidad)
class ComunidadAdmin(admin.ModelAdmin):
    list_display = ["nombre", "rut", "activa"]
    list_filter = ["activa"]
    search_fields = ["nombre", "rut"]
    inlines = [CuentaBancariaInline]


@admin.register(CuentaBancaria)
class CuentaBancariaAdmin(admin.ModelAdmin):
    list_display = ["comunidad", "banco", "numero", "activa"]
    list_filter = ["banco", "activa"]
    search_fields = ["comunidad__nombre", "numero"]
