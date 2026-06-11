from django.db import models
from django.db.models import IntegerField, F, OuterRef, Subquery
from django.db.models.functions import Coalesce

from apps.activity_tracking_app.models.job_post_user_activity_count_model import JobPostUserActivityCountModel
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.job_management_app.models.job_post_model import JobPostModel

class JobPostUserStateManager(models.Manager):
    def with_apply_count(self):
        apply_count_subquery = JobPostUserActivityCountModel.objects.filter(
            job_post_id=OuterRef("job_post_id")
        ).values("apply_count")[:1]

        return (
            self.get_queryset()
            .annotate(
                apply_count=Coalesce(
                    Subquery(apply_count_subquery, output_field=IntegerField()),
                    0
                )
            )
        )

class JobPostUserStateModel(models.Model):
    STATUS_CHOICES = (
        ('saved', 'Saved'),
        ('applied', 'Applied'),
    )

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
        related_name="user_states"
    )
    is_saved = models.BooleanField(default=False)
    save_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)

    objects = JobPostUserStateManager()

    class Meta:
        db_table = "job_post_user_state"
        description = "Job Post User State"
