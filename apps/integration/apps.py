from django.apps import AppConfig


class IntegrationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.integration"

    def ready(self):
        import apps.integration.signals  # noqa: F401  registers post_save → ES
