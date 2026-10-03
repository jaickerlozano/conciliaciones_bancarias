from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.comunidades.views import (
    BancosView,
    ComunidadViewSet,
    CuentaBancariaViewSet,
    PlantillaCartolaView,
)

router = DefaultRouter()
router.register("comunidades", ComunidadViewSet)
router.register("cuentas", CuentaBancariaViewSet)

urlpatterns = [
    path("bancos/", BancosView.as_view()),
    path("plantilla-cartola/", PlantillaCartolaView.as_view()),
    *router.urls,
]
