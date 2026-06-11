from django.apps import AppConfig
from django.db.models.signals import post_migrate
from apps.core.signal import (
    create_default_company,
    create_permissions,
    create_default_role,
)


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        post_migrate.connect(create_default_company)
        post_migrate.connect(create_permissions)
        post_migrate.connect(create_default_role)
        return super().ready()
