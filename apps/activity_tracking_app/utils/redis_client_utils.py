import redis
from django.conf import settings
from django.core.cache import cache

redis_client = cache