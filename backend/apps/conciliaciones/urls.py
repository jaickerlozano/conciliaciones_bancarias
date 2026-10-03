from rest_framework.routers import DefaultRouter

from apps.conciliaciones.views import ConciliacionViewSet

router = DefaultRouter()
router.register("conciliaciones", ConciliacionViewSet)

urlpatterns = router.urls
