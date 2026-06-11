import re
from datetime import datetime
from decimal import Decimal

from django.utils.encoding import force_str, force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from apps.base.constants.base_constants import ExcludeMetaField

from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import string
import secrets

date_format = "%Y-%m-%d"


import phonenumbers


def is_valid_email(email):
    try:
        validate_email(email)
        return True
    except ValidationError:
        return False


# def is_valid_phone_number(phone_number):
#     if str(phone_number).startswith("+"):
#         phone_number = phonenumbers.parse(phone_number)
#     else:
#         phone_number = phonenumbers.parse(phone_number, "KH")
#     return phonenumbers.is_valid_number(phone_number)
def is_valid_phone_number(phone: str) -> bool:
    """Basic E.164-style phone validation. Adjust regex to your needs."""
    return bool(re.match(r"^\+?[1-9]\d{7,14}$", phone))

def to_decimal(value):
    if isinstance(value, Decimal):
        return value

    value = value if value is not None else 0
    return Decimal(value)


def to_int(value):
    if isinstance(value, int):
        return value
    return int(value) if value is not None else 0


def is_new_year(get_date: bool = False):
    dt = datetime.today()
    today = dt.strftime(date_format)
    yearly = datetime(dt.year, 1, 1).strftime(date_format)
    if today == yearly:
        return yearly if get_date else True
    return False


def is_new_month(get_date: bool = False):
    dt = datetime.today()
    today = dt.strftime(date_format)
    monthly = datetime(dt.year, dt.month, 1).strftime(date_format)
    if today == monthly:
        return monthly if get_date else True
    return False


def replace_multi_strings(text: str, replace_obj: dict):
    if not text or not replace_obj:
        return ""
    for i, j in replace_obj.items():
        text = text.replace(i, j)
    return str(text)


def get_date_format(date_time: datetime = None, str_format: str = None):
    if not date_time:
        date_time = datetime.now()
    if str_format:
        return date_time.strftime(str_format)
    return date_time.strftime("%Y-%m-%d")


def get_model_fields_only(model):
    fields = model._meta.get_fields()
    result = []
    for field in fields:
        field_name = field.name
        if not field.is_relation:
            result.append(field_name)
    return result


def separate_value(param):
    field_value = ""
    expression = ""
    default_operator = [
        "like",
        "not_like",
        "equal",
        "not_equal",
        "is_set",
        "is_not_set",
        "true",
        "false",
        "lte",
        "gte",
        "gt",
        "lt",
        "in",
        "not_in",
    ]

    extra_operator = {
        ">": "gt",
        ">=": "gte",
        "<": "lt",
        "<=": "lte",
    }

    if param:
        if isinstance(param, str) and "," in param:
            string = param.split(",", 1)
            expression = string[0].strip()
            field_value = string[1].strip()

        elif param == "is_set" or param == "is_not_set":
            expression = param
        elif param == "true":
            field_value = True
        elif param == "false":
            field_value = False
        else:
            field_value = param

        if expression in extra_operator:
            expression = extra_operator.get(expression, "")

        if expression not in default_operator:
            expression = ""
    return field_value, expression


def get_relationship_field(model):
    result = []
    fields = model._meta.get_fields()
    for field in fields:
        if field.is_relation and hasattr(field, "null") and not field.null:
            result.append(field)
    return result


def convert_internal_value_to_dict(internal_value):
    if isinstance(internal_value, dict):
        return {
            k: convert_internal_value_to_dict(v)
            for k, v in internal_value.items()
            if not k.startswith("_") and k not in ExcludeMetaField.get_exclude_field()
        }
    elif isinstance(internal_value, list) or isinstance(internal_value, tuple):
        return [convert_internal_value_to_dict(v) for v in internal_value]
    elif isinstance(internal_value, set):
        return [convert_internal_value_to_dict(v) for v in list(internal_value)]
    elif hasattr(internal_value, "__dict__"):
        return convert_internal_value_to_dict(internal_value.__dict__)
    else:
        return internal_value


def to_decimal(value):
    if isinstance(value, Decimal):
        return value

    value = value if value is not None else 0
    return Decimal(value)


def to_int(value):
    if isinstance(value, int):
        return value
    return int(value) if value is not None else 0


def encode_uid(pk):
    return force_str(urlsafe_base64_encode(force_bytes(pk)))


def decode_uid(pk):
    return force_str(urlsafe_base64_decode(pk))


def remove_leading_slash(path: str) -> str:
    return path.lstrip("/") if path.startswith("/") else path


def password_generator(length: int = 12):
    """
    Use to generate random password for auth2 user for allow auth2 user login with username and password.
    """
    characters = string.ascii_letters + string.digits + string.punctuation
    password = "".join(secrets.choice(characters) for _ in range(length))
    return password


def get_client_ip(request):
    """
    Use to get client_ip address
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def get_default_company():
    from apps.base.models.company_model import Company

    return Company.objects.filter(code="DEFAULT").first()
