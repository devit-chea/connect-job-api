from rest_framework import serializers

from apps.auth_oauth.serializers.profile_serializer import (
    ApplicantProfileRetrieveSerializer,
)
from apps.job_management_app.models.job_application_model import JobApplicationModel
from apps.job_management_app.selectors.user_company_profile_selector import get_ucp_by_id


class JobStatsQueryParamsSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    month = serializers.IntegerField(required=False, min_value=1, max_value=12)

    def validate(self, data):
        """
        Check that start date is before end date if both are provided.
        """
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError("End date must be after start date.")
        return data


class MonthComparisonStatsSerializer(serializers.Serializer):
    current_month = serializers.IntegerField()
    last_month = serializers.IntegerField()
    trend = serializers.CharField()
    percent_change = serializers.DecimalField(max_digits=5, decimal_places=2)


class JobStatsResponseSerializer(serializers.Serializer):
    total_jobs = serializers.IntegerField()
    active_jobs = serializers.IntegerField()
    closed_jobs = serializers.IntegerField()
    on_hold_jobs = serializers.IntegerField()
    month_comparison = MonthComparisonStatsSerializer()


# Serializer for validating input query parameters
class ApplicantStageQueryParamsSerializer(serializers.Serializer):
    pipeline_id = serializers.IntegerField(required=False)


# Serializer for the nested funnel stage data within the response
class FunnelStageSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    stage_name = serializers.CharField(max_length=100)
    count = serializers.IntegerField()
    order = serializers.IntegerField()
    color = serializers.CharField(max_length=50)


# Serializer for the overall API response structure
class ApplicantHiringStageResponseSerializer(serializers.Serializer):
    pipeline_config_id = serializers.UUIDField()
    total_applicants = serializers.IntegerField()
    total_applicants_by_pipeline = serializers.IntegerField()
    funnel_stages = FunnelStageSerializer(many=True)


class JobApplicationModelSerializer(serializers.ModelSerializer):
    pipeline_step_name = serializers.CharField(read_only=True)
    pipeline_status_name = serializers.CharField(read_only=True)
    applicant_profile = serializers.SerializerMethodField()
    interview_with = serializers.SerializerMethodField()

    class Meta:
        model = JobApplicationModel
        fields = [
            "id",
            "job_post",
            "applicant_name",
            "applicant_current_position",
            "apply_date",
            "status",
            "pipeline_step_name",
            "pipeline_status_name",
            "applicant_profile",
            "create_date",
            "write_date",
            "interview_with",
        ]
        read_only_fields = ["id", "apply_date"]

    def get_applicant_profile(self, obj):
        ucp_id = getattr(obj, "create_ucp_id", None)
        if not ucp_id:
            return None
        
        ucp = get_ucp_by_id(ucp_id)
        if not (ucp and ucp.profile):
            return None
        return ApplicantProfileRetrieveSerializer(
            ucp.profile, context=self.context
        ).data

    def get_interview_with(self, obj):
        """
        Fetch name of the recruiter who created this job via create_ucp_id
        """
        ucp_id = getattr(obj, "create_ucp_id", None)
        if not ucp_id:
            return None

        ucp = get_ucp_by_id(ucp_id)
        if not ucp or not ucp.profile:
            return None

        # Prefer full_name; fallback to first + last
        if ucp.profile.full_name:
            return ucp.profile.full_name

        return f"{ucp.profile.first_name or ''} {ucp.profile.last_name or ''}".strip()
