from __future__ import annotations
import jwt
import logging
from jwt import PyJWTError

from datetime import datetime
from collections import OrderedDict
from datetime import date, datetime
from typing import Dict, List, Optional

from django.contrib.sessions.models import Session
from django.utils import timezone
from rest_framework.authtoken.models import Token


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def bulk_remove_user_session(user_ids):
    for user_id in user_ids:
        session_instances = Session.objects.filter(expire_date__gte=timezone.now())
        for session_instance in session_instances:
            session_data = session_instance.get_decoded()
            if int(session_data["_auth_user_id"]) == user_id:
                session_instance.delete()

        token_instances = Token.objects.filter(user=user_id)
        token_instances.delete()


def increase_email_sequence(email, number_of_created):
    local_part, domain = email.split("@")
    new_local_part = f"{local_part}_inactive" + str(number_of_created + 1)

    return f"{new_local_part}@{domain}"


def calculate_duration_years(start_date, end_date):
    if not start_date:
        return 0
    end = end_date or date.today()
    return (end - start_date).days / 365.25


def parse_date(val):
    if not val:
        return date.min
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val).date()
        except ValueError:
            return date.min

    return date.min


def work_experience_sort_key(item: dict):
    is_current = item.get("is_currently_work", False)

    start_date = parse_date(item.get("start_date"))
    end_date = parse_date(item.get("end_date")) if not is_current else date.max

    return (
        not is_current,
        -end_date.toordinal(),
        -start_date.toordinal(),
    )


def education_sort_key(item: dict):
    is_current = item.get("is_currently_study", False)

    start_date = parse_date(item.get("start_date"))
    end_date = date.max if is_current else parse_date(item.get("end_date"))

    return (
        not is_current,
        -end_date.toordinal(),
        -start_date.toordinal(),
    )


def group_records(
    items: Optional[List[Dict]],
    *,
    obj_key: str,
    name_key: str,
    group_obj_key: str,
    group_name_key: str,
    list_key: str,
    sort_key_fn=None,
) -> List[Dict]:
    groups: "OrderedDict[str, Dict]" = OrderedDict()
    if not items:
        return []

    if sort_key_fn:
        items = sorted(items, key=sort_key_fn)

    for idx, rec in enumerate(items):
        obj_val = rec.get(obj_key)
        name_val = rec.get(name_key) or ""

        if obj_val:
            display = obj_val.get("name") or name_val
            group_key = f"obj:{obj_val.get('id')}"
        elif name_val.strip():
            display = name_val
            group_key = f"name:{name_val.casefold()}"
        else:
            display = ""
            group_key = f"__nogroup__{idx}"

        grp = groups.get(group_key)
        if not grp:
            grp = groups[group_key] = {
                group_name_key: display,
                group_obj_key: obj_val,
                list_key: [],
                "duration": {"years": 0, "months": 0},
                "_total_months": 0,
                "_latest_sort_key": None,
            }

        grp["_total_months"] += _duration_to_months(rec.get("duration", {}))
        grp["duration"] = _months_to_duration(grp["_total_months"])
        grp[list_key].append(rec)

        sort_key = sort_key_fn(rec) if sort_key_fn else None
        if sort_key is not None:
            if grp["_latest_sort_key"] is None or sort_key < grp["_latest_sort_key"]:
                grp["_latest_sort_key"] = sort_key

    result = sorted(
        groups.values(),
        key=lambda g: g.get("_latest_sort_key", sort_key_fn(g[list_key][0])),
    )

    # cleanup
    for g in result:
        g.pop("_total_months", None)
        g.pop("_latest_sort_key", None)

    return result


def group_work_experiences(items: Optional[List[Dict]]) -> List[Dict]:
    return group_records(
        items,
        obj_key="company",
        name_key="company_name",
        group_obj_key="company",
        group_name_key="company_name",
        list_key="experiences",
        sort_key_fn=work_experience_sort_key,
    )


def group_educations(items: Optional[List[Dict]]) -> List[Dict]:
    return group_records(
        items,
        obj_key="institution",
        name_key="institution_name",
        group_obj_key="institution",
        group_name_key="institution_name",
        list_key="educations",
        sort_key_fn=education_sort_key,
    )


def _months_between(start: date, end: date) -> int:
    if end <= start:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day <= start.day:
        months -= 1
    return max(months + 1, 0)


def experience_item_duration(start_date, end_date=None, is_currently: bool = False):
    if not start_date:
        return {"years": 0, "months": 0}
    if end_date is None or is_currently:
        end_date = date.today()

    total_months = _months_between(start_date, end_date)
    years, months = divmod(total_months, 12)
    return {"years": years, "months": months}


def _months_to_duration(total_months: int) -> Dict[str, int]:
    total_months = max(int(total_months or 0), 0)
    y, m = divmod(total_months, 12)
    return {"years": y, "months": m}


def _duration_to_months(duration: Dict[str, int]) -> int:
    y = int(duration.get("years", 0))
    m = int(duration.get("months", 0))
    return y * 12 + m

def jwt_decode_rs256_token(token, public_key):
    try:
        decoded_token = jwt.decode(token, public_key, algorithms=["RS256"])
        return decoded_token
    except PyJWTError as e:
        # Optional: log the exact error
        logger.warning(f"JWT decode failed: {e}")
        return None
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def normalize_date_string(date_str: str) -> str:
    if not date_str:
        return date_str

    date_str = date_str.strip()
    parsed = None

    try:
        parsed = datetime.fromisoformat(date_str.replace("Z", ""))
    except:
        pass

    # Try common formats
    if parsed is None:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(date_str, fmt)
                break
            except:
                continue

    # Parsed → output yyyy-mm-dd
    if parsed:
        return parsed.strftime("%Y-%m-%d")

    # Fallback: return original
    return date_str
