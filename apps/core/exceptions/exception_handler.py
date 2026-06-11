from rest_framework.views import exception_handler as drf_exception_handler

def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    def flatten_errors(errors):
        # Case 1: single message in list → convert to string
        if isinstance(errors, list) and len(errors) == 1 and isinstance(errors[0], str):
            return errors[0]

        # Case 2: list of dicts (e.g. nested serializer validation)
        if isinstance(errors, list) and all(isinstance(e, dict) for e in errors):
            return [flatten_errors(e) for e in errors]

        # Case 3: dict → recurse into children
        if isinstance(errors, dict):
            return {k: flatten_errors(v) for k, v in errors.items()}

        # Case 4: generic list → flatten children
        if isinstance(errors, list):
            return [flatten_errors(e) for e in errors]

        return errors

    if response is not None and isinstance(response.data, dict):
        response.data = flatten_errors(response.data)

        # Move non_field_errors to "detail"
        if "non_field_errors" in response.data:
            response.data["detail"] = response.data.pop("non_field_errors")

    return response
