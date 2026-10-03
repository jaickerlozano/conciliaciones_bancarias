"""Configuración de Django. Todo lo que cambia entre entornos se lee de variables de entorno
(archivo `.env` en la raíz del repo; ver `.env.example`)."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
RAIZ_REPO = BASE_DIR.parent

env = environ.Env()
if (RAIZ_REPO / ".env").exists():
    environ.Env.read_env(RAIZ_REPO / ".env")

DEBUG = env.bool("DJANGO_DEBUG", default=False)
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="solo-desarrollo-no-usar-en-produccion" if DEBUG else environ.Env.NOTSET,
)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=["http://localhost:5173"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.autenticacion",
    "apps.comunidades",
    "apps.conciliaciones",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://conciliaciones:conciliaciones@localhost:5432/conciliaciones",
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "media")))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Archivos subidos (planillas y cartolas)
TAMANO_MAXIMO_ARCHIVO = 10 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = TAMANO_MAXIMO_ARCHIVO + 1024 * 1024

# Sesión por cookie (usuarios internos). El frontend corre en el mismo origen (proxy de Vite).
SESSION_COOKIE_AGE = 60 * 60 * 10  # 10 horas
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # el frontend lee el token para enviarlo en X-CSRFToken
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = not DEBUG

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "EXCEPTION_HANDLER": "config.excepciones.manejar_excepcion",
    "UNAUTHENTICATED_USER": None,
}

# Dónde buscar los archivos reales del cliente (comando demo_cinema y tests)
CONCILIACION_DATOS_DIR = Path(
    env("CONCILIACION_DATOS_DIR", default=str(RAIZ_REPO.parent / "ingresos_egresos_cartolas"))
)
