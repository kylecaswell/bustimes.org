from django.apps import AppConfig


class BusTimesConfig(AppConfig):
    name = 'bustimes'
    verbose_name = 'Bus Times'

    def ready(self):
        from . import signals  # noqa
