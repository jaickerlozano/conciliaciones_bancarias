from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.comunidades.models import CuentaBancaria
from apps.conciliaciones import servicios
from apps.conciliaciones.models import Conciliacion, Cruce, Movimiento, Partida
from apps.conciliaciones.serializers import (
    ArchivoSerializer,
    ConciliacionDetalleSerializer,
    ConciliacionSerializer,
    CrearConciliacionSerializer,
    CruceManualSerializer,
    ReabrirSerializer,
    RedondeoSerializer,
    SubirArchivoSerializer,
)
from motor.dominio import Periodo


class ConciliacionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET    /api/conciliaciones/?cuenta=ID          listado
    POST   /api/conciliaciones/                    {cuenta, periodo: "AAAA-MM"}
    GET    /api/conciliaciones/ID/                 detalle completo
    DELETE /api/conciliaciones/ID/
    POST   /api/conciliaciones/ID/archivos/        multipart {tipo, archivo}
    POST   /api/conciliaciones/ID/procesar/
    POST   /api/conciliaciones/ID/cruces/          {partida, movimiento}  (cruce manual)
    POST   /api/conciliaciones/ID/cruces/CID/confirmar/
    POST   /api/conciliaciones/ID/confirmar-todos/
    DELETE /api/conciliaciones/ID/cruces/CID/
    POST   /api/conciliaciones/ID/redondeo/        {monto}
    POST   /api/conciliaciones/ID/cerrar/
    POST   /api/conciliaciones/ID/reabrir/         {motivo}
    """

    queryset = Conciliacion.objects.select_related("cuenta__comunidad", "cerrada_por")

    def get_serializer_class(self):
        return ConciliacionSerializer if self.action == "list" else ConciliacionDetalleSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        cuenta = self.request.query_params.get("cuenta")
        return qs.filter(cuenta_id=cuenta) if cuenta else qs

    def _detalle(self, conciliacion: Conciliacion, status: int = 200) -> Response:
        conciliacion.refresh_from_db()
        return Response(ConciliacionDetalleSerializer(conciliacion).data, status=status)

    def create(self, request):
        datos = CrearConciliacionSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        cuenta = get_object_or_404(CuentaBancaria, pk=datos.validated_data["cuenta"])
        c = servicios.crear_conciliacion(
            cuenta, Periodo.parse(datos.validated_data["periodo"]), request.user
        )
        return self._detalle(c, status=201)

    def perform_destroy(self, instance):
        servicios.eliminar(instance)

    @action(detail=True, methods=["post"])
    def archivos(self, request, pk=None):
        datos = SubirArchivoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        registro = servicios.guardar_archivo(
            self.get_object(),
            datos.validated_data["tipo"],
            datos.validated_data["archivo"],
            request.user,
        )
        return Response(ArchivoSerializer(registro).data, status=201)

    @action(detail=True, methods=["post"])
    def procesar(self, request, pk=None):
        return self._detalle(servicios.procesar(self.get_object(), request.user))

    @action(detail=True, methods=["post"], url_path="cruces")
    def cruce_manual(self, request, pk=None):
        c = self.get_object()
        datos = CruceManualSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        partida = get_object_or_404(Partida, pk=datos.validated_data["partida"], conciliacion=c)
        movimiento = get_object_or_404(
            Movimiento, pk=datos.validated_data["movimiento"], conciliacion=c
        )
        servicios.cruzar_manual(c, partida, movimiento, request.user)
        return self._detalle(c, status=201)

    def _cruce(self, cruce_id) -> Cruce:
        return get_object_or_404(
            Cruce.objects.select_related("conciliacion", "partida", "movimiento"),
            pk=cruce_id,
            conciliacion=self.get_object(),
        )

    @action(detail=True, methods=["post"], url_path=r"cruces/(?P<cruce_id>\d+)/confirmar")
    def confirmar_cruce(self, request, pk=None, cruce_id=None):
        cruce = servicios.confirmar_cruce(self._cruce(cruce_id), request.user)
        return self._detalle(cruce.conciliacion)

    @action(detail=True, methods=["post"], url_path="confirmar-todos")
    def confirmar_todos(self, request, pk=None):
        c = self.get_object()
        servicios.confirmar_todos(c, request.user)
        return self._detalle(c)

    @action(detail=True, methods=["delete"], url_path=r"cruces/(?P<cruce_id>\d+)")
    def deshacer_cruce(self, request, pk=None, cruce_id=None):
        cruce = self._cruce(cruce_id)
        conciliacion = cruce.conciliacion
        servicios.deshacer_cruce(cruce, request.user)
        return self._detalle(conciliacion)

    @action(detail=True, methods=["post"])
    def redondeo(self, request, pk=None):
        datos = RedondeoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        monto = datos.validated_data["monto"]
        return self._detalle(servicios.ajustar_redondeo(self.get_object(), monto, request.user))

    @action(detail=True, methods=["post"])
    def cerrar(self, request, pk=None):
        return self._detalle(servicios.cerrar(self.get_object(), request.user))

    @action(detail=True, methods=["post"])
    def reabrir(self, request, pk=None):
        datos = ReabrirSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        c = servicios.reabrir(self.get_object(), request.user, datos.validated_data["motivo"])
        return self._detalle(c)
