from django.core.management.commands.runserver import Command as DjangoRunserverCommand


class Command(DjangoRunserverCommand):
    """
    Override default runserver bind for local network testing.
    Now `python manage.py runserver` binds to 0.0.0.0:8000.
    """

    default_addr = "0.0.0.0"
    default_port = "8000"
