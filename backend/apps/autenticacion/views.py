"""Login por sesión de Django. El frontend primero llama a /csrf/ para obtener la cookie."""

from django.contrib.auth import authenticate, login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


def _datos_usuario(usuario) -> dict:
    return {
        "id": usuario.id,
        "usuario": usuario.get_username(),
        "nombre": usuario.get_full_name() or usuario.get_username(),
        "es_admin": usuario.is_staff,
    }


class LoginSerializer(serializers.Serializer):
    usuario = serializers.CharField()
    clave = serializers.CharField(trim_whitespace=False)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(status=204)


# DRF solo exige CSRF a usuarios autenticados; el login también debe exigirlo (login CSRF).
@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        datos = LoginSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        usuario = authenticate(
            request,
            username=datos.validated_data["usuario"],
            password=datos.validated_data["clave"],
        )
        if usuario is None:
            return Response({"detail": "Usuario o clave incorrectos."}, status=400)
        login(request, usuario)
        return Response(_datos_usuario(usuario))


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=204)


class YoView(APIView):
    def get(self, request):
        return Response(_datos_usuario(request.user))
