from rest_framework.routers import DefaultRouter

from apps.comunidades.views import ComunidadViewSet, CuentaBancariaViewSet

router = DefaultRouter()
router.register("comunidades", ComunidadViewSet)
router.register("cuentas", CuentaBancariaViewSet)

urlpatterns = router.urls
