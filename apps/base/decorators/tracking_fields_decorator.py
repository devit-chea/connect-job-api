from functools import wraps

def inject_tracking_fields(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        request = None
        validated_data = None

        for arg in args:
            if hasattr(arg, "user"):
                request = arg
            elif isinstance(arg, dict):
                validated_data = arg

        if "request" in kwargs:
            request = kwargs["request"]
        if "validated_data" in kwargs:
            validated_data = kwargs["validated_data"]

        if not request or not validated_data:
            raise ValueError("inject_tracking_fields decorator expects 'request' and 'validated_data' arguments")

        user = request.user
        user_id = getattr(user, "id", None)
        user_company_profile_id = getattr(request, "user_company_profile_id", None)
        company_id = getattr(request, "company_id", None)

        if "create_uid" not in validated_data:
            validated_data["create_uid"] = user_id
        validated_data["write_uid"] = user_id

        if "create_ucp_id" not in validated_data:
            validated_data["create_ucp_id"] = user_company_profile_id
        validated_data["write_ucp_id"] = user_company_profile_id

        if "company_id" not in validated_data:
            validated_data["company_id"] = company_id

        return func(*args, **kwargs)

    return wrapper
