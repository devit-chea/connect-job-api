from rest_framework import serializers

from apps.activity_tracking_app.models.job_post_user_activity_count_model import (
    JobPostUserActivityCountModel,
)


class JobPostUserActivityCountSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPostUserActivityCountModel
        fields = ["job_post_id", "view_count", "save_count", "apply_count"]
