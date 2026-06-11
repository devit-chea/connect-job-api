from apps.core.base.request_decorator import request_cache
from apps.core.base.setting_utils import Settings


@request_cache
def get_bool(request, name, company_id=None):
    return Settings.get_bool(name, company_id)


@request_cache
def get_str(request, name, company_id=None):
    return Settings.get_str(name, company_id)
