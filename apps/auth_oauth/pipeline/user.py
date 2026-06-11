import uuid

from apps.auth_oauth.constants.auth_constants import (
    ProfileStatus,
    UserStatus,
    UserTypes,
)
from apps.auth_oauth.services.user_company_profile_service import (
    UserCompanyProfileService,
)
from apps.base.utils.base_util import get_default_company
from social_core.utils import module_member, slugify
from uuid import uuid4

USER_FIELDS = ["username", "email", "first_name", "last_name"]


def save_profile(backend, user, response, *args, **kwargs):
    user_type = backend.strategy.session_get("user_type") or None
    default_company = get_default_company()
    default_company_id = (
        default_company.pk
        if default_company and user_type == UserTypes.APPLICANT
        else None
    )
    data = {
        "user": user,
        "status": ProfileStatus.ACTIVE,
        "type": user_type,
        "provider": backend.name,
        "image_url": response.get("picture", ""),
        "company": default_company_id,
    }

    user_company_profile = UserCompanyProfileService.social_create(data)
    if not user.default_user_profile_company:
        user.default_user_profile_company = (
            user_company_profile.pk if user_company_profile else None
        )


def create_user(strategy, details, backend, user=None, *args, **kwargs):
    if user and user.status != UserStatus.DELETED:
        return {"is_new": False}
    fields = {
        name: kwargs.get(name, details.get(name))
        for name in backend.setting("USER_FIELDS", USER_FIELDS)
    }
    # 2.fallback apple
    fields["first_name"] = fields.get("first_name") or " "
    fields["last_name"] = fields.get("last_name") or " "
    email = fields.get("email")
    if not email:
        provider_id = kwargs.get("sub") or kwargs.get("provider_id") or uuid.uuid4().hex
        email = f"{provider_id}@appleuser.com"
    if not fields:
        return None
    fields["email"] = (
        email.lower() if backend.setting("FORCE_EMAIL_LOWERCASE", False) else email
    )
    fields["login_type"] = "social"
    if not fields.get("username"):
        fields["username"] = (
            kwargs.get("sub")
            or kwargs.get("provider_id")
            or f"apple_{uuid.uuid4().hex[:8]}"
        )
    return {"is_new": True, "user": strategy.create_user(**fields)}


def get_username(strategy, details, backend, user=None, *args, **kwargs):
    if "username" not in backend.setting("USER_FIELDS", USER_FIELDS):
        return None
    storage = strategy.storage

    if not user:
        email_as_username = backend.setting("USERNAME_IS_FULL_EMAIL", False)
        uuid_length = backend.setting("UUID_LENGTH", 16)
        max_length = storage.user.username_max_length()
        do_slugify = backend.setting("SLUGIFY_USERNAMES", False)
        do_clean = backend.setting("CLEAN_USERNAMES", True)

        def identity_func(val):
            return val

        if do_clean:
            override_clean = backend.setting("CLEAN_USERNAME_FUNCTION")
            if override_clean:
                clean_func = module_member(override_clean)
            else:
                clean_func = storage.user.clean_username
        else:
            clean_func = identity_func

        if do_slugify:
            override_slug = backend.setting("SLUGIFY_FUNCTION")
            slug_func = module_member(override_slug) if override_slug else slugify
        else:
            slug_func = identity_func

        if email_as_username and details.get("email"):
            username = details["email"]
        elif details.get("username"):
            username = details["username"]
        else:
            username = uuid4().hex

        short_username = (
            username[: max_length - uuid_length] if max_length is not None else username
        )
        final_username = slug_func(clean_func(username[:max_length]))

        # Generate a unique username for current user using username
        # as base but adding a unique hash at the end. Original
        # username is cut to avoid any field max_length.
        # The final_username may be empty and will skip the loop.
        while not final_username or storage.user.user_exists(username=final_username,status__in=["active", "inactive"]):
            username = short_username + uuid4().hex[:uuid_length]
            final_username = slug_func(clean_func(username[:max_length]))
    else:
        final_username = storage.user.get_username(user)
    return {"username": final_username}

