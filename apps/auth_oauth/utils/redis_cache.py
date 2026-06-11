import json
import logging
from typing import Any, Dict, Optional

from django.conf import settings
from redis.exceptions import RedisError
from django.core.cache import cache

# Logger setup
logger = logging.getLogger(__name__)

# Constants
DEFAULT_CACHE_ALIAS = "default"
SENTINEL_CACHE_ALIAS = "sentinel"

# Default configurations
DEFAULT_PERMISSION_CACHE_KEY_TEMPLATE = (
    "permissions:user:{user_id}:ucp:{user_company_profile_id}"
)
DEFAULT_PERMISSION_CACHE_TTL = 60 * 15  # 15 minutes

# Settings
CACHE_ENABLED = getattr(settings, "AUTH_PERMISSION_CACHE_ENABLED", False)
CACHE_URL = getattr(settings, "REDIS_URL", None)


def get_cached_json(key: str) -> Optional[Dict[str, Any]]:
    """Retrieves and parses a JSON object from Redis."""
    try:
        value = cache.get(key)
        return json.loads(value) if value else None
    except (json.JSONDecodeError, RedisError) as e:
        logger.warning(f"Failed to retrieve/parse cache for key {key}: {e}")
        return None


def set_cached_json(key: str, value: Any, ttl: Optional[int] = None) -> bool:
    """Stores a JSON-serializable object with an expiration (TTL)."""
    
    # Fallback to default TTL if not provided
    timeout = ttl or get_permission_cache_ttl()

    try:
        return cache.set(key, json.dumps(value), timeout)
    except (TypeError, RedisError) as e:
        logger.error(f"Failed to cache data for key {key}: {e}")
        return False


def delete_cached_key(key: str) -> bool:
    """Removes a key from Redis."""
    try:
        return bool(cache.delete(key))
    except RedisError as e:
        logger.error(f"Failed to delete key {key}: {e}")
        return False


# --- Permission Specific Helpers ---


def get_permission_cache_key(user_id: int, user_company_profile_id: int) -> str:
    """Generates a formatted cache key for user permissions."""
    template = getattr(
        settings,
        "AUTH_PERMISSION_CACHE_KEY_TEMPLATE",
        DEFAULT_PERMISSION_CACHE_KEY_TEMPLATE,
    )
    return template.format(
        user_id=user_id, user_company_profile_id=user_company_profile_id
    )


def get_permission_cache_ttl() -> int:
    """Returns TTL from settings or default global constant."""
    return getattr(settings, "PERMISSION_CACHE_TTL", DEFAULT_PERMISSION_CACHE_TTL)
