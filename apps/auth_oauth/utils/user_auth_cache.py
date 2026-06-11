import logging
from typing import Any, Optional
from django.core.cache import cache as redis_client

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)



def set_cached_value(key: str, value: Any, timeout: Optional[int] = None) -> None:
    """
    Safely set a value in the Redis cache.
    """
    if redis_client is None:
        logger.debug(f"Redis client not available. Skipping set for key: {key}")
        return

    try:
        redis_client.set(key, value, timeout)
        logger.debug(f"Set cache key: {key}")
    except Exception as e:
        logger.warning(f"Failed to set cache key {key}: {e}")


def get_cached_value(key: str, default: Any = None) -> Any:
    """
    Safely get a value from the Redis cache.
    """
    if redis_client is None:
        logger.debug(f"Redis client not available. Returning default for key: {key}")
        return default

    try:
        value = redis_client.get(key)
        logger.debug(f"Retrieved cache key: {key}")
        return value if value is not None else default
    except Exception as e:
        logger.warning(f"Failed to get cache key {key}: {e}")
        return default


def delete_cached_key(key: str) -> None:
    """
    Safely delete a key from the Redis cache.
    """
    if redis_client is None:
        logger.debug(f"Redis client not available. Skipping delete for key: {key}")
        return

    try:
        redis_client.delete(key)
        logger.debug(f"Deleted cache key: {key}")
    except Exception as e:
        logger.warning(f"Failed to delete cache key {key}: {e}")


def has_cached_key(key: str) -> bool:
    """
    Check if a key exists in the Redis cache.
    """
    if redis_client is None:
        logger.debug(f"Redis client not available. Cannot check key: {key}")
        return False

    try:
        return redis_client.has_key(key)
    except Exception as e:
        logger.warning(f"Failed to check existence of cache key {key}: {e}")
        return False
