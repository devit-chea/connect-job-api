import logging
from urllib.parse import urlparse, urlunparse

from pydash import to_boolean
from apps.base.models.sys_setting_model import SysSetting
from config.settings import base
from config.settings.base import API_BASE_URL, WEB_BASE_URL

CONST_DEFAULT_TO_EMAIL = "DEFAULT_TO_EMAIL"
CONST_DEFAULT_FROM_EMAIL = "DEFAULT_FROM_EMAIL"
CONST_ENABLE_REAL_EMAIL = "ENABLE_REAL_EMAIL"

class Settings:
    @staticmethod
    def get_system_setting(setting_name, company_id=None):
        try:
            val = SysSetting.objects.get(name=setting_name, company=company_id).value
            return val
        except SysSetting.DoesNotExist:
            return getattr(base, setting_name)

    @staticmethod
    def get_bool(name, company_id=None):
        value = Settings.get_system_setting(name, company_id)
        if value:
            return to_boolean(value.lower())
        return False

    @staticmethod
    def get_str(name, company_id=None):
        return Settings.get_system_setting(name, company_id)

    @staticmethod
    def get_int(name, company_id=None):
        value = Settings.get_system_setting(name, company_id)
        if value and str.isdigit(value):
            return int(value)
        logging.info("Can not convert system setting value to int.")
        return 0


def replace_hostname(url, new_hostname):
    parsed_url = urlparse(url)
    new_netloc = (
        new_hostname if parsed_url.port is None else f"{new_hostname}:{parsed_url.port}"
    )
    new_url = urlunparse(parsed_url._replace(netloc=new_netloc))
    return new_url


def get_web_base_url():
    return WEB_BASE_URL


def get_api_base_url():
    return API_BASE_URL
