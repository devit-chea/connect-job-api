from config.settings.base import API_BASE_URL

from config.settings import base


class DefaultSettings(object):

    HTTP_IP_ADDRESS_HEADER = "REMOTE_ADDR"
    HTTP_USER_AGENT_HEADER = "HTTP_USER_AGENT"

    COMPANY_MODEL = "base.Company"
    AUTH_USER_MODEL = "apps.auth_oauth.User"

    OTP_VERIFY_ATTEMPT_LIMIT = 3
    OTP_RETRY_IN_SECONDS = 60 * 1  # in seconds
    OTP_EXPIRY_IN_SECONDS = 60 * 2  # in seconds
    DEFAULT_FROM_EMAIL = getattr(base, "DEFAULT_FROM_EMAIL")
    PASSWORD_ENCRYPTION = getattr(base, "PASSWORD_ENCRYPTION")

    ENABLE_AUTH_TOTP_MAIL = False
    AUTH_TOTP_MAIL_TEMPLATE_CONTEXT = {
        "logo_login_alert": f"{API_BASE_URL}/static/assets/logo_login_alert.png",
        "logo_transparency": f"{API_BASE_URL}/static/assets/logo_transparency.png",
    }


class Settings(object):
    def __getattr__(self, name):
        setting = getattr(DefaultSettings, name)
        return setting


settings = Settings()
