from config.settings.base import *  # noqa: F401, F403

# ── Local development overrides ───────────────────────────────────────────────
# Use this settings file when running against a plain local Redis instance
# instead of the Sentinel cluster used in dev/prod.
#
# Set in your shell or .env:
#   DJANGO_SETTINGS_MODULE=config.settings.local
#
# Or rely on manage.py which defaults to config.settings.dev — you can
# override per-run with:
#   DJANGO_SETTINGS_MODULE=config.settings.local python manage.py runserver

DEBUG = True

# Force standalone Redis regardless of what REDIS_USE_SENTINEL says in .env
REDIS_USE_SENTINEL = False

_REDIS_HOST = env.str("REDIS_HOST", "127.0.0.1")
_REDIS_PORT = env.int("REDIS_PORT", 6379)
_REDIS_PASSWORD = env.str("REDIS_PASSWORD", "")

# Override REDIS_URL to a simple standalone URL if not explicitly set
REDIS_URL = env.str("REDIS_URL", f"redis://{_REDIS_HOST}:{_REDIS_PORT}/1")

# Re-declare CACHES with DefaultClient (base.py already conditions on
# REDIS_USE_SENTINEL, but since we override it here after import we must
# also re-declare CACHES to pick up the new value).
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "PASSWORD": _REDIS_PASSWORD,
        },
    }
}

# Celery — point straight at local Redis, no transport options needed
CELERY_BROKER_URL = env.str(
    "CELERY_BROKER_URL",
    f"redis://{_REDIS_HOST}:{_REDIS_PORT}/0",
)
CELERY_RESULT_BACKEND = env.str(
    "CELERY_RESULT_BACKEND",
    f"redis://{_REDIS_HOST}:{_REDIS_PORT}/2",
)
CELERY_BROKER_TRANSPORT_OPTIONS = {}
CELERY_BROKER_USE_SSL = {}

# Email — console backend so no SMTP needed locally
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
