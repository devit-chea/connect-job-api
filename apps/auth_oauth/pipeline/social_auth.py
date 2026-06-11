from django.contrib.auth import get_user_model
from social_core.exceptions import AuthAlreadyAssociated

from apps.auth_oauth.constants.auth_constants import UserStatus

User = get_user_model()


def social_user(backend, uid, user=None, *args, **kwargs):
    provider = backend.name
    social = backend.strategy.storage.user.get_social_auth(provider, uid)
    is_delete = False
    if social:
        if user and social.user != user:
            raise AuthAlreadyAssociated(backend)
        if social.user and social.user.status == UserStatus.DELETED:
            social.delete()
            is_delete = True
        if not user:
            user = social.user if social.user != UserStatus.DELETED else None
    else:
        # If no social account is found, check if a user with the same email exists
        email = kwargs.get("details", {}).get("email")
        if email and user is None:
            try:
                # Find the existing user by email, ensure they are active/not deleted
                existing_user = User.objects.get(email=email, status=UserStatus.ACTIVE)
                user = existing_user
                backend.strategy.storage.user.create_social_auth(
                    existing_user, uid, backend.name
                )
            except User.DoesNotExist:
                pass
    social = social if not is_delete else None
    return {
        "social": social,
        "user": user,
        "is_new": user is None,
        "new_association": social is None,
    }
