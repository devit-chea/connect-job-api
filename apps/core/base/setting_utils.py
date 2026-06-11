from django.conf import settings


def strtobool(val: str) -> bool:
    """Simple replacement for distutils.util.strtobool"""
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return True
    elif val in ("n", "no", "f", "false", "off", "0"):
        return False
    else:
        raise ValueError(f"Invalid truth value: {val}")


class Settings:
    @classmethod
    def get_system_setting(cls, setting_name: str, default=None):
        return getattr(settings, setting_name, default)

    @classmethod
    def get_bool(cls, name: str, default: bool = False) -> bool:
        value = cls.get_system_setting(name)
        if value is not None and isinstance(value, str):
            try:
                return bool(strtobool(value))
            except ValueError:
                return default
        return bool(value) if value is not None else default

    @classmethod
    def get_str(cls, name: str, default: str = "") -> str:
        value = cls.get_system_setting(name, default)
        return str(value) if value is not None else default
