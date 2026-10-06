"""`runserver` con puerto propio del proyecto (8010) para no chocar con otros proyectos Django
que usan el 8000. Mantiene el comportamiento de staticfiles. Se puede pasar otro puerto igual
que siempre: `runserver 9000`."""

from django.contrib.staticfiles.management.commands.runserver import Command as RunserverBase


class Command(RunserverBase):
    default_port = "8010"
