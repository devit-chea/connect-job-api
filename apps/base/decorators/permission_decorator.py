from functools import wraps

from apps.auth_oauth.constants.auth_constants import PermissionOptions
from apps.auth_oauth.services.permission_service import PermissionService
from apps.base.mixins.permission_mixin import (
    ensure_applicant_profile_complete,
)
from apps.core.exceptions.base_exceptions import PermissionDeniedException


def permission(permission_codename=None, allow_pending=False):
    """
    Decorator to check if the user has the required permission type.
    ex:
        @permission("codename")
        def create():
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            request = args[1] if hasattr(args[0], "__class__") else args[0]

            permissions = PermissionService.fetch_permissions(request)
            permission_type = PermissionService().check_permission(
                permissions, permission_codename
            )

            if permission_type == PermissionOptions.DENIED:
                raise PermissionDeniedException("Access denied.")

            if (
                permission_type == PermissionOptions.VIEW_ONLY
                and request.method != "GET"
            ):
                raise PermissionDeniedException("Read-only access.")

            ensure_applicant_profile_complete(request, skip=allow_pending)

            return view_func(*args, **kwargs)

        return wrapped_view

    return decorator
