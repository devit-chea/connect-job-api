import os
from datetime import timedelta
from pathlib import Path

from environs import Env

from apps.core.utils import parse_sentinels

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = Env()
env.read_env()

ENV = env("DJANGO_ENV", "dev")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env.str("DJANGO_SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DJANGO_DEBUG", False)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

CORS_ALLOW_CREDENTIALS = env.bool("CORS_ALLOW_CREDENTIALS", False)
CORS_ORIGIN_ALLOW_ALL = env.bool("CORS_ORIGIN_ALLOW_ALL", False)
CORS_ORIGIN_WHITELIST = env.list("CORS_ORIGIN_WHITELIST", default=[])

SINGLE_USE_TOKEN_SECRET = env.str("SINGLE_USE_TOKEN_SECRET", "")
RESET_PASS_TOKEN_EXPIRY_SECONDS = int(env("RESET_PASS_TOKEN_EXPIRY_SECONDS", 900))

DEFAULT_PASSWORD = env.str("DEFAULT_PASSWORD", "password123")
TIME_RESET_FAIL_LOGIN_MINUTES = env.int(
    "SECURITY_LOGIN_THROTTLING_TIME_RESET_FAIL_LOGIN_MINUTE", 10
)
PASSWORD_EXPIRE_MINUTES = env.int("SECURITY_PASSWORD_EXPIRE_MINUTES", 100)
FAIL_LOGIN_COUNT = env.int("SECURITY_LOGIN_THROTTLING_FAIL_LOGIN_COUNT", 10)

# file
ALLOWED_EXTENSIONS = env.list("FILE_UPLOAD_ALLOWED_EXTENSIONS", default=[])
FILE_MAX_SIZE = env.int("FILE_UPLOAD_MAX_SIZE_MB", 100)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "django_rest_passwordreset",
    "rest_framework.authtoken",
    # auth 2
    "oauth2_provider",
    "social_django",
    "drf_social_oauth2",
    # Apps
    "apps.core",
    "apps.base",
    "apps.auth_oauth",
    "apps.auth_setting",
    "apps.auth_totp_mail",
    "apps.configuration",
    "apps.recruiter_management",
    "apps.job_management_app",
    "apps.file_management_app",
    # Elasticsearch
    "django_elasticsearch_dsl",
    "django_elasticsearch_dsl_drf",
    "django_celery_beat",
    "apps.activity_tracking_app",
    "apps.notification_app",
    "apps.elasticsearch_app",
    "wdg_core_file_storage.wdg_file_metadata",
    "wdg_storage.file_metadata",
    "apps.dashboard",
    "apps.integration",
    "django_structlog",
    # Audit Log
    "auditlog",
]

MIDDLEWARE = [
    "django_structlog.middlewares.RequestMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_user_agents.middleware.UserAgentMiddleware",
    "apps.core.middleware.jwt_middleware.RemoveExpiredJwtMiddleware",
    "apps.core.middleware.jwt_middleware.JwtCookieAccessTokenMiddleware",
    "apps.core.middleware.security_headers.SecurityHeadersMiddleware",
    "apps.core.middleware.audilog_middleware.JWTAuditlogMiddleware",
]
ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "social_django.context_processors.backends",
                "social_django.context_processors.login_redirect",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env.str("DB_NAME"),
        "USER": env.str("DB_USER"),
        "PASSWORD": env.str("DB_PASSWORD"),
        "HOST": env.str("DB_HOST"),
        "PORT": env.str("DB_PORT"),
    }
}

# # Elasticsearch
ELASTICSEARCH_DSL = {
    'default': {
        'hosts': env.list('ES_URLS', []),
        'http_auth': (
            env.str("ES_USERNAME"),
            env.str("ES_PASSWORD"),
        ),
    }
}

# Mail Configuration
# https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = env.str(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = env.str("EMAIL_HOST", "")
EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD", "")
EMAIL_HOST_USER = env.str("EMAIL_HOST_USER", "")
EMAIL_PORT = env.int("EMAIL_PORT", 587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = env.str("EMAIL_DEFAULT_FROM_EMAIL", "")
DEFAULT_TO_EMAIL = env.str("EMAIL_DEFAULT_TO_EMAIL", "")
ENABLE_REAL_EMAIL = env.bool("EMAIL_ENABLE_REAL_EMAIL", False)
IS_SEND_DEFAULT_PASSWORD = env.bool("EMAIL_IS_SEND_DEFAULT_PASSWORD", False)

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = env.str("TIME_ZONE", "UTC")

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-requested-with",
    "wdg-url-path",
    "X-CSRFToken",
    "scope",
    # 'x-csrftoken',
    "credentials",
]

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.auth_oauth.authentication.CustomJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": ["rest_framework.filters.OrderingFilter"],
    "EXCEPTION_HANDLER": "apps.core.exceptions.exception_handler.exception_handler",
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.CustomPagination",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Swagger",
    "DESCRIPTION": "Swagger API",
    "VERSION": "1.0.0",
    "SCHEMA_PATH_PREFIX": "/api",
    "SERVE_INCLUDE_SCHEMA": False,
    "SECURITY": [
        {
            "jwtAuth": [],
        }
    ],
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "jwtAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
    "SWAGGER_UI_SETTINGS": """{
        deepLinking: true,
        filter: true,
        presets: [
            SwaggerUIBundle.presets.apis, 
            SwaggerUIStandalonePreset
        ],
        layout: "StandaloneLayout",
    }""",
}

SIMPLE_JWT = {
    "ALGORITHM": "RS256",
    "AUTH_HEADER_TYPES": ("Bearer", "JWT"),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "ACCESS_COOKIE": env.str("JWT_ACCESS_COOKIE", ""),
    "REFRESH_COOKIE": env.str("JWT_REFRESH_COOKIE"),
    "ACCESS_TOKEN_LIFETIME": timedelta(
        seconds=env.int("JWT_ACCESS_TOKEN_LIFETIME_SECONDS")
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        seconds=env.int("JWT_REFRESH_TOKEN_LIFETIME_SECONDS")
    ),
    "SIGNING_KEY": env.str("JWT_SIGNING_KEY").replace("\\n", "\n").encode(),
    "VERIFYING_KEY": env.str("JWT_VERIFYING_KEY").replace("\\n", "\n").encode(),
    "BLACKLIST_AFTER_ROTATION": True,
    "ROTATE_REFRESH_TOKENS": True,
    "COOKIE_SECURE": env.bool("JWT_COOKIE_SECURE"),  # Ensures HTTPS only
    "COOKIE_HTTP_ONLY": env.bool("JWT_COOKIE_HTTP_ONLY"),  # Prevents JavaScript access
    "COOKIE_SAMESITE": env.str("JWT_COOKIE_SAMESITE"),  # # Controls cross-site behavior
    "COOKIE_DOMAIN": env.str("JWT_COOKIE_DOMAIN"),  # Available for subdomains
}

AUTH_USER_MODEL = "auth_oauth.User"

# --- Redis Settings ---
REDIS_USE_SENTINEL = env.bool("REDIS_USE_SENTINEL", default=False)
REDIS_HOST = env.str("REDIS_HOST", "localhost")
REDIS_PORT = env.int("REDIS_PORT", 6379)
REDIS_URL = env.str("REDIS_URL", None)
REDIS_PASSWORD = env.str("REDIS_PASSWORD", "123456")
RESULT_EXPIRES = env.int("REDIS_RESULT_EXPIRES")

REDIS_FLUSH_INTERVAL_SECONDS = env.int("REDIS_FLUSH_INTERVAL_SECONDS", 300)

# --- TLS / mTLS settings ---
REDIS_SSL_CA_CERTS = env.str("REDIS_SSL_CA_CERTS", "/etc/valkey/tls/ca.crt")
REDIS_SSL_CERT_FILE = env.str("REDIS_SSL_CERT_FILE", "/etc/valkey/tls/client.crt")
REDIS_SSL_KEY_FILE = env.str("REDIS_SSL_KEY_FILE", "/etc/valkey/tls/client.key")
REDIS_SSL_CERT_REQS = env.str("REDIS_SSL_CERT_REQS", "required")

DIRTY_FLUSH_INTERVAL_SECONDS = env.int("DIRTY_FLUSH_INTERVAL_SECONDS", 300)

REDIS_SENTINELS = parse_sentinels(env.str("REDIS_SENTINELS", None))
REDIS_SENTINEL_MASTER = env.str("REDIS_SENTINEL_MASTER", "mymaster")
REDIS_SENTINEL_PASSWORD = env.str("REDIS_SENTINEL_PASSWORD", None)
REDIS_SSL = env.bool("REDIS_SSL", default=False)

REDIS_SSL_OPTIONS = {
    "ssl": True,
    "ssl_check_hostname": False,
    "ssl_cert_reqs": env.str("REDIS_SSL_CERT_REQS", "required"),
    "ssl_ca_certs": env.str("REDIS_SSL_CA_CERTS", "/etc/valkey/tls/ca.crt"),
    "ssl_certfile": env.str("REDIS_SSL_CERT_FILE", "/etc/valkey/tls/client.crt"),
    "ssl_keyfile": env.str("REDIS_SSL_KEY_FILE", "/etc/valkey/tls/client.key"),
} if REDIS_SSL else {}

CACHES = {
    "default": {
        # Use the standard django-redis backend
        "BACKEND": "django_redis.cache.RedisCache",
        # LOCATION must follow this format for Sentinel
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.SentinelClient",
            "CONNECTION_FACTORY": "apps.core.sentinel.SentinelConnectionFactory",
            "SENTINELS": REDIS_SENTINELS,
            "SENTINEL_KWARGS": {
                "password": REDIS_SENTINEL_PASSWORD,
                **REDIS_SSL_OPTIONS,
            },
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 100,
                **REDIS_SSL_OPTIONS,
            },
            "PASSWORD": REDIS_PASSWORD,
        }
    }
}

CELERY_BROKER_TRANSPORT_OPTIONS = {
    "master_name": REDIS_SENTINEL_MASTER,
    "password": REDIS_PASSWORD,
    "sentinel_kwargs": {
        "password": REDIS_SENTINEL_PASSWORD,
        **REDIS_SSL_OPTIONS
    },
    "connection_kwargs": {
        "password": REDIS_PASSWORD,
        **REDIS_SSL_OPTIONS,
    }
}

CELERY_BROKER_URL = env.str("CELERY_BROKER_URL", None)
CELERY_BROKER_USE_SSL = REDIS_SSL_OPTIONS
CELERY_RESULT_BACKEND = env.str("CELERY_RESULT_BACKEND", None)

CELERY_TASK_ACKS_LATE = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

IMAGEKIT_CACHEFILE_DIR = "storages/thumbnails/"

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "")

STATIC_URL = "/api/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STATIC_ASSET_URL = "/static/"
STATIC_ASSET_ROOT = os.path.join(BASE_DIR, "static")

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
STATICFILES_DIRS = [
    BASE_DIR / "static",
]

FILE_ACCESS_TIMEOUT = env.int("FILE_ACCESS_TIMEOUT", 60 * 15)
FILE_THUMBNAIL_UUID_URL = "storages/thumbnails/uuid/"
FILE_ACCESS_LIFETIME = env.int("FILE_ACCESS_LIFETIME", 60 * 15)

API_BASE_URL = env.str("APP_URLS_API_BASE")
WEB_BASE_URL = env.str("APP_URLS_WEB_BASE")
WEB_BASE_URL_LOGIN = env.str("APP_URLS_WEB_BASE_LOGIN")
WEB_BASE_URL_CONTACT_US = env.str(
    "WEB_BASE_URL_CONTACT_US", "https://connectjob.connectkh.com/en/contact-us"
)

AUTHENTICATION_BACKENDS = [
    "social_core.backends.google.GoogleOAuth2",
    "drf_social_oauth2.backends.LinkedInOpenIDUserInfo",
    "drf_social_oauth2.backends.DjangoOAuth2",
    "social_core.backends.apple.AppleIdAuth",
    "django.contrib.auth.backends.ModelBackend",
]

USERNAME_IS_FULL_EMAIL = True

# Google configuration
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = env.str(
    "AUTH_PROVIDERS_WEB_CLIENT_GOOGLE_OAUTH2_CLIENT_ID", ""
)
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = env.str(
    "AUTH_PROVIDERS_WEB_CLIENT_GOOGLE_OAUTH2_CLIENT_SECRET", ""
)
SOCIAL_AUTH_GOOGLE_OAUTH2_REDIRECT_URI = env.str(
    "AUTH_PROVIDERS_WEB_CLIENT_GOOGLE_OAUTH2_REDIRECT_URI", ""
)

SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_KEY = env.str(
    "AUTH_PROVIDERS_WEB_CLIENT_LINKEDIN_OPENIDCONNECT_CLIENT_ID", ""
)
SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_SECRET = env.str(
    "AUTH_PROVIDERS_WEB_CLIENT_LINKEDIN_OPENIDCONNECT_CLIENT_SECRET"
)
SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_REDIRECT_URI = env.str(
    "AUTH_PROVIDERS_WEB_CLIENT_LINKEDIN_OPENIDCONNECT_REDIRECT_URI", ""
)

# mobile client
# google android
MOBILE_SOCIAL_AUTH_GOOGLE_OAUTH2_KEY_ANDROID = env.str(
    "AUTH_PROVIDERS_MOBILE_CLIENT_GOOGLE_ANDROID_OATH2_CLIENT_ID", ""
)
# google ios
MOBILE_SOCIAL_AUTH_GOOGLE_OAUTH2_KEY_IOS = env.str(
    "AUTH_PROVIDERS_MOBILE_CLIENT_GOOGLE_IOS_OATH2_CLIENT_ID"
)

# linkedin
MOBILE_SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_KEY = env.str(
    "AUTH_PROVIDERS_MOBILE_CLIENT_LINKEDIN_OPENIDCONNECT_CLIENT_ID", ""
)
MOBILE_SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_SECRET = env.str(
    "AUTH_PROVIDERS_MOBILE_CLIENT_LINKEDIN_OPENIDCONNECT_CLIENT_SECRET", ""
)
MOBILE_SOCIAL_AUTH_LINKEDIN_OPENIDCONNECT_REDIRECT_URI = env.str(
    "AUTH_PROVIDERS_MOBILE_CLIENT_LINKEDIN_OPENIDCONNECT_REDIRECT_URI", ""
)

SOCIAL_AUTH_APPLE_ID_CLIENT = env("SOCIAL_AUTH_APPLE_ID_CLIENT")  # Service ID
SOCIAL_AUTH_APPLE_ID_REDIRECT_URI = env("SOCIAL_AUTH_APPLE_ID_REDIRECT_URI")
SOCIAL_AUTH_APPLE_TEAM_ID = env("SOCIAL_AUTH_APPLE_TEAM_ID")
SOCIAL_AUTH_APPLE_KEY_ID = env("SOCIAL_AUTH_APPLE_KEY_ID")
SOCIAL_AUTH_APPLE_PRIVATE_KEY = env("SOCIAL_AUTH_APPLE_PRIVATE_KEY").replace(
    "\\n", "\n"
)
SOCIAL_AUTH_APPLE_BUNDLE_ID = env("SOCIAL_AUTH_APPLE_BUNDLE_ID")
SOCIAL_AUTH_APPLE_CLIENT = SOCIAL_AUTH_APPLE_BUNDLE_ID
AUDIENCE = SOCIAL_AUTH_APPLE_BUNDLE_ID
SOCIAL_AUTH_APPLE_AUDIENCE = ["com.wingdigital.wingcareer.dev"]
# Define SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE to get extra permissions from Google.
SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
SOCIAL_AUTH_IMMUTABLE_USER_FIELDS = (
    "first_name",
    "last_name",
)

SILENCED_SYSTEM_CHECKS = ["auth.W004"]

LIMIT_RESEND_OTP = env.int("OTP_LIMIT_RESEND", 3)

# WDG NOTIFICATION SERVICE
WDG_NOTIFICATION_BASE_URL = env.str("WDG_NOTIFICATION_BASE_URL", None)
WDG_NOTIFICATION_APP_ID = env.str("WDG_NOTIFICATION_APP_ID", None)
WDG_NOTIFICATION_SECRET_KEY = env.str("WDG_NOTIFICATION_SECRET_KEY", None)
WDG_NOTIFICATION_IS_ENABLE = env.bool("WDG_NOTIFICATION_IS_ENABLE", False)
WDG_NOTIFICATION_EMAIL = env.str("WDG_NOTIFICATION_EMAIL", "connectjob@connectkh.com")

# S3 by PowerScale
S3_ACCESS_KEY_ID = env("S3_ACCESS_KEY_ID", default=None)
S3_SECRET_ACCESS_KEY = env("S3_SECRET_ACCESS_KEY", default=None)
S3_STORAGE_BUCKET_NAME = env("S3_STORAGE_BUCKET_NAME", default=None)
S3_BUCKET_NAME = env.str("S3_BUCKET_NAME", default=None)
S3_ENDPOINT_URL = env("S3_ENDPOINT_URL", default=None)
S3_REGION_NAME = None
S3_PRESIGNED_EXPIRE = env("S3_PRESIGNED_EXPIRE", default=3600)

# Wdg File Storage
AWS_S3_ACCESS_KEY_ID = env.str("AWS_S3_ACCESS_KEY_ID", "")
AWS_S3_SECRET_ACCESS_KEY = env.str("AWS_S3_SECRET_ACCESS_KEY", "")
AWS_STORAGE_BUCKET_NAME = env.str("AWS_STORAGE_BUCKET_NAME", "")
AWS_S3_ENDPOINT_URL = env.str("AWS_S3_ENDPOINT_URL", "")
AWS_S3_REGION_NAME = None
AWS_S3_PRESIGN_EXPIRE = env.int("AWS_S3_PRESIGN_EXPIRE", 3600)

# WDG Storage configs
WDG_STORAGE_SAVE_METADATA = env.bool("WDG_STORAGE_SAVE_METADATA", True)
WDG_STORAGE_PATH = env.str("WDG_STORAGE_PATH", "job_platform")
WDG_STORAGE_PROXY_URL = env.str("WDG_STORAGE_PROXY_URL", "")

# PERMISSION CATCHING
AUTH_PERMISSION_CACHE_ENABLED = env.bool("AUTH_PERMISSION_CACHE_ENABLED", False)
CACHE_REDIS_URL = REDIS_URL

# auth2 pipeline
SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    # 'social_core.pipeline.social_auth.social_user',
    'apps.auth_oauth.pipeline.social_auth.social_user',
    'apps.auth_oauth.pipeline.user.get_username',
    'social_core.pipeline.social_auth.associate_by_email',
    # 'social_core.pipeline.user.create_user',
    'apps.auth_oauth.pipeline.user.create_user',
    'apps.auth_oauth.pipeline.user.save_profile',
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',

)

# CV Scan
CV_SCAN_URL = env.str("CV_SCAN_URL", "")
CV_SCAN_SECRET_KEY = env.str("CV_SCAN_SECRET_KEY", "")
CV_SCAN_GET_TOKEN_URL = env.str("CV_SCAN_GET_TOKEN_URL", "")
CV_SCAN_BASIC_TOKEN = env.str("CV_SCAN_BASIC_TOKEN", "")

# Password Encryption
PASSWORD_ENCRYPTION = env.bool("PASSWORD_ENCRYPTION", default=False)
AUTH_PUBLIC_KEY = env.str("AUTH_PUBLIC_KEY", "")
AUTH_PRIVATE_KEY = env.str("AUTH_PRIVATE_KEY", "")
AUTH_PASSWORD_ENCRYPTION = env.bool("AUTH_PASSWORD_ENCRYPTION", default=False)

# Tow step verification
TWO_STEP_VERIFICATION = env.bool("TWO_STEP_VERIFICATION", False)

# Rate limit
RATE_LIMITS = {
    "SIGNUP_RECRUITER": {
        "LIMIT": 3,
        "PERIOD": 60 * 10,
    },
    "SIGNUP_APPLICANT": {
        "LIMIT": 3,
        "PERIOD": 60 * 10,
    },
    "RESET_PASSWORD": {
        "LIMIT": 3,
        "PERIOD": 60 * 10,
    },
}

# ALTCHA(reCAPTCHA) Configuration
ALTCHA_DESIRED_MAX_NUMBER = env.int("ALTCHA_DESIRED_MAX_NUMBER", 750000)
ALTCHA_HMAC_KEY = env.str("ALTCHA_HMAC_KEY", "")
ALTCHA_EXPIRY = env.int("ALTCHA_EXPIRY", 60 * 5)
APP_NAME = env.str("APP_NAME", "job-platform-api")
from config.logging.log_config import *
# settings.py
SOCIAL_AUTH_APPLE_ID_EXTRA_DATA = [
    ('refresh_token', 'refresh_token'),
    ('id_token', 'id_token'),
    ('expires_in', 'expires'),
]
SOCIAL_AUTH_APPLE_DISCONNECT_PIPELINE = True
SOCIAL_AUTH_DISCONNECT_PIPELINE = (
    'social_core.pipeline.disconnect.allowed_to_disconnect',
    'social_core.pipeline.disconnect.get_entries',
    'social_core.pipeline.disconnect.revoke_tokens',
    'social_core.pipeline.disconnect.disconnect',
)
TELEGRAM_BOT_TOKEN     = env.str("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_BOT_USERNAME  = env.str("TELEGRAM_BOT_USERNAME", default="job_platform_dev_bot")
TELEGRAM_WEBHOOK_SECRET = env.str("TELEGRAM_WEBHOOK_SECRET", default="your-random-secret-here")

# TELEGRAM OIDC
TELEGRAM_CLIENT_ID = env.str("TELEGRAM_CLIENT_ID", "")
TELEGRAM_CLIENT_SECRET = env.str("TELEGRAM_CLIENT_SECRET", "")
TELEGRAM_TOKEN_URI = env.str(
    "TELEGRAM_TOKEN_URI", "https://oauth.telegram.org/token"
)
TELEGRAM_JWKS_URI = env.str("TELEGRAM_JWKS_URI", "https://oauth.telegram.org/.well-known/jwks.json")
TELEGRAM_REDIRECT_URI  = env.str("TELEGRAM_REDIRECT_URI", "https://dev-connectjob.connectkh.com/api/auth/telegram/callback")
TELEGRAM_MOBILE_REDIRECT_URI  = env.str("TELEGRAM_MOBILE_REDIRECT_URI", "")

# Mobile App Force Update
IOS_MIN_VERSION = env.str("IOS_MIN_VERSION", default="1.1.0")
ANDROID_MIN_VERSION = env.str("ANDROID_MIN_VERSION", default="1.1.0")

APP_STORE_URL = env.str("APP_STORE_URL", default="")
PLAY_STORE_URL = env.str("PLAY_STORE_URL", default="")

# AUDIT LOG CONFIGURATION
# Enable global tracking across all models automatically
AUDITLOG_INCLUDE_ALL_MODELS = True

# Exclude specific internal Django / third-party apps from being tracked
AUDITLOG_EXCLUDE_TRACKING_MODELS = (
    "admin",
    "auth",
    "contenttypes",
    "sessions",
    "messages",
    "staticfiles",
    "django_celery_beat.PeriodicTasks",
)

# Globally ignore specific fields across ALL tracked models.
AUDITLOG_EXCLUDE_TRACKING_FIELDS = (
    "create_date",
    "write_date",
    "create_uid",
    "write_uid",
)
# integration key
CONNECTOR_INTEGRATION_KEY = env.str("CONNECTOR_INTEGRATION_KEY", None)
CONNECTOR_INTEGRATION_URL = env.str("CONNECTOR_INTEGRATION_URL", None)
