from django.db import connection

from django.conf import settings


def add_tenant_schema(logger, log_method, event_dict):
    try:
        tenant = getattr(connection, "tenant", None)
        if tenant:
            event_dict["schema_name"] = tenant.schema_name
        else:
            event_dict["schema_name"] = "public"
    except Exception:
        event_dict["schema_name"] = "unknown"

    return event_dict


def add_app_name(logger, log_method, event_dict):
    event_dict["app_name"] = getattr(settings, "APP_NAME", "job-platform-api")
    return event_dict
