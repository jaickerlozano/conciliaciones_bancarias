from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Conciliaciones — Gaudi Administraciones"
admin.site.site_title = "Conciliaciones"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.autenticacion.urls")),
    path("api/", include("apps.comunidades.urls")),
    path("api/", include("apps.conciliaciones.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
