from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string
from django_redis.pool import ConnectionFactory


class SentinelConnectionFactory(ConnectionFactory):
    """
        Custom Redis Sentinel connection factory.

        Based on: https://github.com/jazzband/django-redis/issues/663
        Adds support for custom pool, Sentinel config, and SSL handling.
    """

    def __init__(self, options):
        # allow overriding the default SentinelConnectionPool class
        super().__init__(options)
        pool_cls_path = options.setdefault(
            "CONNECTION_POOL_CLASS", "redis.sentinel.SentinelConnectionPool"
        )
        self.pool_cls = import_string(pool_cls_path)
        self.pool_cls_kwargs = options.get("CONNECTION_POOL_KWARGS", {})

        sentinel_cls_path = options.get("SENTINEL_CLASS", "redis.sentinel.Sentinel")
        self.sentinel_cls = import_string(sentinel_cls_path)

        redis_client_cls_path = options.get("REDIS_CLIENT_CLASS", "redis.client.Redis")
        self.redis_client_cls = import_string(redis_client_cls_path)

        connection_pool_cls_path = options.get(
            "CONNECTION_POOL_CLASS", "redis.sentinel.SentinelConnectionPool"
        )
        self.connection_pool_cls = import_string(connection_pool_cls_path)

        self.redis_client_cls_kwargs = options.get("REDIS_CLIENT_KWARGS", {})

        self.options = options

        sentinels = options.get("SENTINELS")
        if not sentinels:
            raise ImproperlyConfigured(
                "SENTINELS must be provided as a list of (host, port)."
            )

        self.min_other_sentinels = options.get("MIN_OTHER_SENTINELS", 0)
        self.sentinel_kwargs = options.get("SENTINEL_KWARGS", {})

        # provide the connection pool kwargs to the sentinel in case it
        # needs to use the socket options for the sentinels themselves
        connection_kwargs = self.make_connection_params(None)
        connection_kwargs.pop("url")
        connection_kwargs.update(self.pool_cls_kwargs)
        self.connection_kwargs = connection_kwargs
        self._sentinel = self.sentinel_cls(
            sentinels,
            self.min_other_sentinels,
            self.sentinel_kwargs,
            **self.connection_kwargs,
        )

    def get_connection_pool(self, params):
        url = urlparse(params["url"])
        master_name = url.hostname

        if master_name is None:
            raise ValueError(
                'SENTINEL_SETTINGS["master_name"] must be specified in the Django settings.'
            )

        pool = self.connection_pool_cls(
            master_name, self._sentinel, **self.connection_kwargs
        )

        return pool
