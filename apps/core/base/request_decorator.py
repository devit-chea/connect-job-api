from functools import wraps


def request_cache(func):
    """
    The cache data is store on current request and cleared automatically at the end of the request lifecycle
    """

    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request:
            return func(request, *args, **kwargs)

        user_id = request.user.id if request.user else None
        cache_key = f"{user_id}_{func.__name__}_{args}_{kwargs}"

        if not hasattr(request, "_cache"):
            setattr(request, "_cache", {})

        if cache_key in request._cache:
            return request._cache[cache_key]

        result = func(request, *args, **kwargs)
        request._cache[cache_key] = result

        return result

    return wrapper
