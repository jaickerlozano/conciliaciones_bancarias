"""Admin de solo lectura: las conciliaciones se modifican únicamente vía servicios (API),
para que se respeten las reglas de negocio y quede registro en la bitácora."""

from django.contrib import admin

from apps.conciliaciones.models import ArchivoCargado, Conciliacion, Evento


class SoloLectura:
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ArchivoInline(SoloLectura, admin.TabularInline):
    model = ArchivoCargado
    fields = ["tipo", "nombre_original", "tamano", "subido_por", "subido_en"]
    readonly_fields = fields
    extra = 0


class EventoInline(SoloLectura, admin.TabularInline):
    model = Evento
    fields = ["fecha", "usuario", "accion", "detalle"]
    readonly_fields = fields
    extra = 0


@admin.register(Conciliacion)
class ConciliacionAdmin(SoloLectura, admin.ModelAdmin):
    list_display = ["cuenta", "anio", "mes", "estado", "procesada_en", "cerrada_en"]
    list_filter = ["estado", "cuenta__banco"]
    search_fields = ["cuenta__comunidad__nombre"]
    inlines = [ArchivoInline, EventoInline]
