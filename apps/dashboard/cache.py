import json
import hashlib
from typing import Any
from apps.activity_tracking_app.utils.redis_client_utils import redis_client


def make_key(*parts: Any) -> str:
    key_string = "|".join(map(str, parts))
    hashed_key = hashlib.sha256(key_string.encode()).hexdigest()
    return "dashboard:" + hashed_key


def get_cache(key):
    v = redis_client.get(key)
    if not v:
        return None
    return json.loads(v)


def set_cache(key, value, ttl=60 * 5):
    redis_client.set(key, json.dumps(value), ex=ttl)


def delete_cache(pattern):
    # naive pattern deletion
    for k in redis_client.scan_iter(match=f"dashboard*{pattern}*"):
        redis_client.delete(k)
