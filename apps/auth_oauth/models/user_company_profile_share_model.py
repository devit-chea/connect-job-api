from django.db import models
from django.db.models import Q

from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.soft_delete_model import SoftDeleteModel


class UserCompanyProfileShareModel(AbstractBaseModel, SoftDeleteModel):
    """
    Grants one UserCompanyProfile (viewer_ucp) read-only visibility into
    another UserCompanyProfile record (target_ucp) — the SHARED branch of
    RolePermission.record_scope. "Who shared it" is the inherited
    create_ucp_id, same convention as JobPostAssignedRecruiterModel.
    """

    target_ucp = models.ForeignKey(
        UserCompanyProfile,
        on_delete=models.CASCADE,
        related_name="visibility_shares_as_target",
    )
    viewer_ucp = models.ForeignKey(
        UserCompanyProfile,
        on_delete=models.CASCADE,
        related_name="visibility_shares_as_viewer",
    )

    class Meta:
        db_table = "user_company_profile_shares"
        constraints = [
            models.UniqueConstraint(
                fields=["target_ucp", "viewer_ucp"],
                condition=Q(is_deleted=False),
                name="uniq_active_ucp_share",
            )
        ]
