from typing import Iterable

from apps.auth_oauth.constants.auth_constants import UserTypes, DefaultRole
from apps.auth_oauth.models.role_model import Role
from django.db import transaction

from apps.auth_oauth.models.user_company_profile import UserCompanyProfile


class UserRoleService:

    @staticmethod
    def get_default_roles(user_type: str) -> Iterable[Role]:
        qs = Role.objects.all()
        return qs.filter(type=user_type, is_default=True)

    @staticmethod
    def get_social_default_roles(user_type: str) -> Iterable[Role]:
        if user_type == UserTypes.ADMIN_RECRUITER:
            qs = Role.objects.filter(code=DefaultRole.PENDING_ADMIN_RECRUITER_ROLE)
            return qs
        return Role.objects.filter(type=user_type, is_default=True)


    @staticmethod
    @transaction.atomic
    def promote_pending_admin_to_full(ucp: UserCompanyProfile) -> bool:
        """If ucp has PENDING role, swap to FULL Admin Recruiter."""
        full = Role.objects.filter(code=DefaultRole.ADMIN_RECRUITER_ROLE).first()
        pending = Role.objects.filter(code=DefaultRole.PENDING_ADMIN_RECRUITER_ROLE).first()
        if not full:
            return False

        changed = False
        if pending and ucp.roles.filter(pk=pending.pk).exists():
            ucp.roles.remove(pending)
            changed = True

        if not ucp.roles.filter(pk=full.pk).exists():
            ucp.roles.add(full)
            changed = True
        return changed
