from django.urls import path

from apps.autenticacion.views import CsrfView, LoginView, LogoutView, YoView

urlpatterns = [
    path("csrf/", CsrfView.as_view()),
    path("login/", LoginView.as_view()),
    path("logout/", LogoutView.as_view()),
    path("yo/", YoView.as_view()),
]
