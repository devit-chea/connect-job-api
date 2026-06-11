from apps.auth_oauth.utils.auth_util import get_user_agent_info
from apps.auth_oauth.models.permission_model import Permission
from apps.core.exceptions.base_exceptions import PermissionDeniedException
from apps.auth_oauth.constants.auth_constants import PermissionOptions, ProfileStatus
from apps.auth_oauth.serializers.auth_serializer import PermissionSerializer
from config.settings.base import AUTH_PERMISSION_CACHE_ENABLED
from apps.auth_oauth.utils.redis_cache import (
    get_permission_cache_key,
    get_cached_json,
    set_cached_json,
    get_permission_cache_ttl,
)


class PermissionService:

    @staticmethod
    def fetch_permissions(request):
        """fetch permission"""

        user_company_profile_id = None
        user_id = None

        # Check if the user is authenticated
        if request.user and request.user.is_authenticated:
            # Try to get user_company_profile_id from user object or auth payload
            user_company_profile_id = getattr(
                request.user,
                "user_company_profile_id",
                request.auth.payload.get("user_company_profile_id"),
            )
            user_id = request.user.id

        # Attempt to retrieve permissions from cache
        if AUTH_PERMISSION_CACHE_ENABLED:
            cache_key = get_permission_cache_key(
                user_id=user_id, user_company_profile_id=user_company_profile_id
            )
            if cache_key:
                permissions = get_cached_json(cache_key)
                if permissions:
                    return permissions

        # Fetch permissions from service
        queryset, context = PermissionService().get_user_roles_and_permissions(request)
        data = PermissionSerializer(queryset, many=True, context=context).data

        # Cache the permissions if enabled
        if AUTH_PERMISSION_CACHE_ENABLED and data:
            cache_key = get_permission_cache_key(
                user_id=user_id, user_company_profile_id=user_company_profile_id
            )
            if cache_key:
                set_cached_json(cache_key, data, ttl=get_permission_cache_ttl())

        return data

    @staticmethod
    def get_user_roles_and_permissions(request):
        """
        Retrieves the user's roles and associated top-level permissions.
        Returns a queryset of permissions and a context dictionary.
        """
        roles = []

        # Try to get user_company_profile_id from auth payload
        user_company_profile_id = request.auth.payload.get("user_company_profile_id")

        # Fallback to user agent info if not found
        if not user_company_profile_id:
            user_agent = get_user_agent_info(request.user, request)
            user_company_profile_id = (
                user_agent.get("user_company_profile_id") if user_agent else None
            )

        # Get active user company profile instance
        user_company_profile_instance = request.user.user_company_profile_user.filter(
            id=user_company_profile_id, status=ProfileStatus.ACTIVE
        ).last()

        # Get roles from the  profile instance
        if user_company_profile_instance:
            roles = user_company_profile_instance.roles.all()

        # Fetch top-level permissions associated with the roles
        queryset = Permission.objects.filter(
            role_permissions_related__role_id__in=roles
        ).distinct()

        context = {"request": request, "roles": roles}

        return queryset, context

    @staticmethod
    def check_permission(permissions, codename):
        """
        Validates if the given codename(s) has permission in the provided permissions list.
        Raises PermissionDeniedException if access is denied or permission is not found.
        """
        if permissions is None or codename is None:
            raise ValueError("Permissions list and codename cannot be None.")

        perm_types_found = set()

        def search(perms):
            total_checked = 0

            for perm in perms:
                total_checked += 1
                if perm is None:
                    continue

                current_codename = perm.get("codename")
                perm_type = perm.get("perm_type")

                # Handle list of codenames
                if isinstance(codename, list):
                    if current_codename in codename and perm_type in (
                        PermissionOptions.ALLOWED,
                        PermissionOptions.DENIED,
                        PermissionOptions.VIEW_ONLY,
                    ):
                        perm_types_found.add(perm_type)

                # Handle single codename
                elif current_codename == codename:
                    if perm_type == PermissionOptions.DENIED:
                        raise PermissionDeniedException(
                            f"Access denied for permission: {codename}"
                        )
                    elif perm_type in (
                        PermissionOptions.ALLOWED,
                        PermissionOptions.VIEW_ONLY,
                    ):
                        return perm_type

                # Recursively check children
                children = perm.get("children")
                if children:
                    result = search(children)
                    if result:
                        return result

            priority_order = {
                PermissionOptions.ALLOWED: 0,
                PermissionOptions.DENIED: 1,
                PermissionOptions.VIEW_ONLY: 2,
            }
            sorted_types = sorted(perm_types_found, key=priority_order.get)
            return (
                sorted_types[0]
                if sorted_types and total_checked == len(permissions)
                else None
            )

        result = search(permissions)

        if result == PermissionOptions.ALLOWED:
            return None
        elif result == PermissionOptions.VIEW_ONLY:
            return PermissionOptions.VIEW_ONLY
        elif result == PermissionOptions.DENIED:
            raise PermissionDeniedException(f"Access denied for permission: {codename}")
        else:
            raise PermissionDeniedException(
                f"Permission {codename} not found. Access denied by default."
            )
