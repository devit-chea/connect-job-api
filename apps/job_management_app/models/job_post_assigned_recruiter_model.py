from django.db import models

from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.soft_delete_model import SoftDeleteModel
from apps.job_management_app.models.job_post_model import JobPostModel


class JobPostAssignedRecruiterModel(AbstractBaseModel,SoftDeleteModel):
    job_post = models.ForeignKey(
        JobPostModel,
        on_delete=models.CASCADE,
        related_name="job_post_assigned_recruiters",
    )
    assigned_ucp = models.ForeignKey(
        UserCompanyProfile,
        on_delete=models.CASCADE,
        related_name="assigned_job_posts",
    )

    class Meta:
        db_table = "job_post_assigned_recruiter"