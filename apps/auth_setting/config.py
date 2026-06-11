from apps.auth_setting.setting import settings
from apps.base.models.sys_setting_model import SysSetting


class Configs:

    @staticmethod
    def _setting(setting_name, company=None) -> any:
        try:
            value = SysSetting.objects.get(name=setting_name, company_id=company).value
        except SysSetting.DoesNotExist:
            value = getattr(settings, setting_name)
        return value

    @staticmethod
    def _bool_setting(setting_name, company=None) -> bool:
        value = Configs._setting(setting_name, company)
        if value:
            return Configs.strtobool(value)
        return False

    @staticmethod
    def _int_setting(setting_name, company=None) -> int:
        value = Configs._setting(setting_name, company)
        return int(value)

    @staticmethod
    def strtobool(val):
        val = val.lower()
        if val in ("y", "yes", "t", "true", "on", "1"):
            return True
        elif val in ("n", "no", "f", "false", "off", "0"):
            return False
        else:
            raise ValueError(f"Invalid truth value {val}")
