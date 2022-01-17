from django.apps import AppConfig


class ClientsConfig(AppConfig):
    name = 'clients'
    verbose_name = "Settings"

    def ready(self):
        import clients.signals



