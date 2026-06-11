import logging
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from apps.auth_oauth.constants.auth_constants import UserState

User = get_user_model()

logger = logging.getLogger(__name__)

class UserCleanupService:
    """
    Service to clean up users who did not complete profile setup
    """

    @staticmethod
    def get_expired_incomplete_users(hours: int = 25):
        threshold = timezone.now() - timedelta(hours=hours)
        return User.objects.filter(
            date_joined__lte=threshold,
            is_active=True,
            status="active",
        ).filter(
            Q(user_company_profile_user__profile__isnull=True) |
            Q(user_company_profile_user__state=UserState.PENDING_SETUP_PROFILE)
        ).distinct().prefetch_related(
            "user_company_profile_user__profile"
        )

    @staticmethod
    @transaction.atomic
    def delete_users(queryset, hard_delete: bool = False) -> int:
        """
        Delete users safely
        """
        count = queryset.count()
        
        if hard_delete:
            logger.info(f"Cleaned {count} incomplete users(hard delete).")
            queryset.delete()
        else:
            logger.info(f"Cleaned {count} incomplete users(soft delete).")
            queryset.update(is_active=False, status="deleted")

        return count

    @classmethod
    def cleanup_incomplete_users(
        cls,
        hours: int = 25,
        hard_delete: bool = False,
    ) -> int:
        """
        Main entrypoint
        """
        qs = cls.get_expired_incomplete_users(hours=hours)

        return cls.delete_users(qs, hard_delete=hard_delete)