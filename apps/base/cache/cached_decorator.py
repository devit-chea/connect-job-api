from threading import Lock
from functools import wraps
from . import caches_util

# Create a dictionary to hold the locks
lock_dict = {}


def cached(timeout=None, exclude_args=[], exclude_kwargs=[]):
    """
    A decorator for caching function results with a timeout.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            
            args_to_cache = [arg for i, arg in enumerate(args) if i not in exclude_args]
            kwargs_to_cache = {key: value for key, value in kwargs.items() if key not in exclude_kwargs}
            
            cache_key = caches_util.generate_cache_key(func.__name__, args_to_cache, kwargs_to_cache)

            # Get the lock for this cache key
            if cache_key not in lock_dict:
                lock_dict[cache_key] = Lock()
            lock = lock_dict[cache_key]

            cached_result = caches_util.get_from_cache(cache_key)
            if cached_result is not None:
                return cached_result

            # Acquire the lock to prevent race conditions
            lock.acquire()
            try:
                # Check the cache again to see if another thread has already computed the result
                cached_result = caches_util.get_from_cache(cache_key)
                if cached_result is not None:
                    return cached_result

                result = func(*args, **kwargs)
                caches_util.store_in_cache(cache_key, result, timeout)

            finally:
                # Release the lock
                lock.release()

            return result

        return wrapper

    return decorator
