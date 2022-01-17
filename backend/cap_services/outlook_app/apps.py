from django.apps import AppConfig


class OutlookAppConfig(AppConfig):
    name = 'outlook_app'

    def ready(self):
        import outlook_app.signals
