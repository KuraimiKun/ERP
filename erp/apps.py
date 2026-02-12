from django.apps import AppConfig


class ErpConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'erp'
    verbose_name = 'ERP System'

    def ready(self):
        """Import signals when app is ready."""
        pass  # Signals can be imported here when needed

