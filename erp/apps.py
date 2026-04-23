from django.apps import AppConfig


class ErpConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "erp"
    verbose_name = "ERP System"

    def ready(self):
        """Import signals when app is ready."""
        import erp.signals  # noqa: F401 – connect audit signals
