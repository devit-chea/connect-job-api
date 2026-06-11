import logging
import time
from functools import wraps

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from apps.activity_tracking_app.utils.redis_client_utils import redis_client

logger = logging.getLogger(__name__)


def rate_limit(key_prefix: str):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(self, request, *args, **kwargs):
            cfg = settings.RATE_LIMITS.get(key_prefix.upper())
            if not cfg:
                raise RuntimeError(
                    f"RATE_LIMITS config not found for key_prefix '{key_prefix}'"
                )

            limit = cfg.get("LIMIT")
            period = cfg.get("PERIOD")

            ip = request.META.get("REMOTE_ADDR", "unknown")

            # Smart identifier selection
            if request.method == "GET":
                identifier = request.query_params.get("email", "").lower()
            else:
                identifier = (
                    request.data.get("email") or request.data.get("username") or ""
                )
                identifier = str(identifier).lower()

            key = f"rl:{key_prefix}:{identifier}"

            try:
                # --------------------------------------------------
                # 1) Check current count WITHOUT increasing
                # --------------------------------------------------
                current = redis_client.get(key)
                current = int(current) if current else 0

                # If already reached limit → block WITHOUT increment
                if current >= limit:
                    logger.warning(
                        "Rate limit exceeded: %s %s %s", key_prefix, ip, identifier
                    )
                    return Response(
                        {"detail": "Please try again later."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # --------------------------------------------------
                # 2) Otherwise INCR (first safe to increment)
                # --------------------------------------------------
                new_count = redis_client.incr(key)
                if new_count == 1:  # first hit
                    redis_client.expire(key, period)

            except Exception as exc:
                logger.exception("Redis rate limiter error: %s", exc)

            return view_func(self, request, *args, **kwargs)

        return _wrapped

    return decorator


# ----------- CLIENT IP EXTRACTION -----------
def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


# ----------- SLIDING WINDOW LOGIC -----------
def sliding_window_check(key, limit, period):
    now = int(time.time() * 1000)  # ms precision
    window_start = now - (period * 1000)

    pipeline = redis_client.pipeline()

    # Add the current request timestamp
    pipeline.zadd(key, {str(now): now})

    # Remove outdated timestamps
    pipeline.zremrangebyscore(key, 0, window_start)

    # Count how many remain (== number of requests in window)
    pipeline.zcard(key)

    # Set TTL (not mandatory but good cleanup)
    pipeline.expire(key, period)

    _, _, count, _ = pipeline.execute()

    return count


# ----------- DECORATOR -----------
def rate_limit_sliding(key_prefix: str):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(self, request, *args, **kwargs):

            cfg = settings.RATE_LIMITS.get(key_prefix.upper())
            if not cfg:
                raise RuntimeError(f"RATE_LIMITS config missing for '{key_prefix}'")

            limit = cfg["LIMIT"]
            period = cfg["PERIOD"]

            ip = get_client_ip(request)

            if request.method == "GET":
                identifier = request.query_params.get("email", "")
            else:
                identifier = (
                    request.data.get("email") or request.data.get("username") or ""
                )
            identifier = identifier.lower().strip()

            ip_key = f"sl:{key_prefix}:ip:{ip}"
            id_key = f"sl:{key_prefix}:id:{identifier}" if identifier else None

            try:
                # -------------------------
                # IP RATE LIMIT
                # -------------------------
                ip_count = sliding_window_check(ip_key, limit, period)
                if ip_count > limit:
                    logger.warning("Sliding IP limit exceeded %s %s", key_prefix, ip)
                    return Response(
                        {"detail": "Please try again later."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # -------------------------
                # IDENTIFIER RATE LIMIT
                # -------------------------
                if id_key:
                    id_count = sliding_window_check(id_key, limit, period)
                    if id_count > limit:
                        logger.warning(
                            "Sliding ID limit exceeded %s %s", key_prefix, identifier
                        )
                        return Response(
                            {"detail": "Please try again later."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

            except Exception as e:
                logger.exception("Sliding window rate limiter error: %s", e)
                return view_func(self, request, *args, **kwargs)

            return view_func(self, request, *args, **kwargs)

        return _wrapped

    return decorator
