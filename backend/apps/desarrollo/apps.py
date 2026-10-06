from django.apps import AppConfig


class DesarrolloConfig(AppConfig):
    """Utilidades de desarrollo local (puerto propio de runserver)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.desarrollo"
