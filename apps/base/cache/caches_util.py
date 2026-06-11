import hashlib
from django.core.cache import cache
import json
from typing import Any, Dict, Tuple

def store_in_cache(key, obj, timeout=None):
    cache.set(key, obj, timeout)


def get_from_cache(key):
    return cache.get(key)


def generate_cache_key(func_name: str, args: Tuple[Any, ...], kwargs: Dict[str, Any] = None) -> str:
    if kwargs is None:
        kwargs = {}

    args_repr = str(args)
    kwargs_repr = json.dumps(kwargs, sort_keys=True)
    
    data_to_hash = (args_repr + kwargs_repr).encode("utf-8")
    
    args_hash = hashlib.sha256(data_to_hash).hexdigest()
    
    return func_name + args_hash

def delete_range(pattern):
    all_keys = cache._cache.keys()
    copy_keys = list(all_keys)
    for key in copy_keys:
        if pattern in key:
            actual_key = key.split(":")[-1]
            cache.delete(actual_key)


def get_range(pattern):
    all_keys = cache._cache.keys()
    copy_keys = list(all_keys)
    return [
        {"key": key.split(":")[-1], "value": get_from_cache(key.split(":")[-1])}
        for key in copy_keys
        if pattern in key
    ]

def get_all_keys():
    all_keys = cache._cache.keys()
    copy_keys = list(all_keys)
    return copy_keys
