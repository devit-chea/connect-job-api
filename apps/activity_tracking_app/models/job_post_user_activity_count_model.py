from django.db import models

from apps.job_management_app.models.job_post_model import JobPostModel


class JobPostUserActivityCountModel(models.Model):
    job_post = models.OneToOneField(
        JobPostModel,
        on_delete=models.CASCADE,
        related_name="user_activity_count",
    )
    view_count = models.PositiveIntegerField(default=0)
    save_count = models.PositiveIntegerField(default=0)
    apply_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "job_post_user_activity_count"
        description = "Job Post User Activity Count"
