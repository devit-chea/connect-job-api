from django.apps import AppConfig


class ElasticsearchAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.elasticsearch_app"

    def ready(self):
        import apps.elasticsearch_app.signals.signals
