from django.db import models
from django.utils.timezone import now

from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.activity_tracking_app.constants.job_activity_types import ActivityTrackingTypes
from apps.job_management_app.models.job_post_model import JobPostModel


class JobPostUserEventModel(models.Model):
    user_company_profile = models.ForeignKey(
        UserCompanyProfile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    job_post = models.ForeignKey(
        JobPostModel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    activity_type = models.CharField(choices=ActivityTrackingTypes.choices, max_length=50)
    create_date = models.DateTimeField(auto_now_add=True)
    create_date_date = models.DateField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.create_date:
            self.create_date_date = self.create_date.date()
        else:
            self.create_date_date = now().date()
        super().save(*args, **kwargs)

    class Meta:
        db_table = "job_post_user_event"
        description = "Job Post User Event"
        indexes = [
            models.Index(fields=['user_company_profile_id', 'job_post_id', 'activity_type']),
            models.Index(fields=['activity_type', 'create_date']),
        ]
        unique_together = (
            'user_company_profile', 'job_post', 'activity_type', 'create_date',
        )
