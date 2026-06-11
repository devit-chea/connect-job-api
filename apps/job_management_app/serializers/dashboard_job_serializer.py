import logging

from rest_framework import serializers

from apps.activity_tracking_app.serializers.activity_count_serializer import JobPostUserActivityCountSerializer
from apps.elasticsearch_app.services.applicant_recommend_service import (
    get_recommended_applicants,
)
from apps.job_management_app.models.job_post_model import JobPostModel
from apps.base.decorators.datetime_format_decorator import datetime_format_decorator, DateTimeFormat


logger = logging.getLogger(__name__)


@datetime_format_decorator(
    fields=["post_date", "create_date", "write_date"],
    field_formats={"post_date": DateTimeFormat.DEFAULT},
    use_timezone=True,
)
class JobPostListSerializer(serializers.ModelSerializer):
    recommended_count = serializers.SerializerMethodField()
    activity_count = serializers.SerializerMethodField()
    
    class Meta:
        model = JobPostModel
        fields = [
            "id",
            "title",
            "post_date",
            "expire_date",
            "priority",
            "status",
            "recommended_count",
            "activity_count",
            "location",
            "time_type",
            "remote_type",
        ]

    # Recommended Count
    def get_recommended_count(self, obj):
        """
        Calculates and returns the count of applicants with matching scores
        above the threshold for this job post, using the ES service.
        """
        try:
            # We call the service but discard the detailed list, we only need the count.
            _, count = get_recommended_applicants(
                job_post=obj, min_score_threshold=5, is_job_state=False
            )
            return count
        except Exception as e:
            return 0  # Default to 0 on failure

    @staticmethod
    def get_activity_count(obj):
        if hasattr(obj, "user_activity_count") and obj.user_activity_count:
            return JobPostUserActivityCountSerializer(obj.user_activity_count).data
        return {"view_count": 0, "save_count": 0, "apply_count": 0}