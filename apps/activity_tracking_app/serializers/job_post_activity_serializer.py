from rest_framework import serializers

from apps.activity_tracking_app.constants.job_activity_types import (
    ActivityTrackingTypes,
)
from apps.activity_tracking_app.models.job_post_user_state_model import (
    JobPostUserStateModel,
)
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.base.decorators.datetime_format_decorator import datetime_format_decorator
from apps.base.serializers.base_serializer import (
    BaseCompanySerializer,
    BaseDecimalRangeSerializerField,
)
from apps.base.utils.auth_utils import get_user_company_profile_id
from apps.job_management_app.models.job_post_model import JobPostModel


class JobPostActivitySerializer(serializers.Serializer):
    ACTIVITY_CHOICES = (
        ("save", "Save"),
        ("unsave", "Unsave"),
        ("apply", "Apply"),
    )

    job_post_id = serializers.IntegerField()
    activity_type = serializers.ChoiceField(choices=ACTIVITY_CHOICES)

    def validate(self, data):

        request = self.context["request"]
        job_post_id = data["job_post_id"]
        activity_type = data["activity_type"]

        try:
            job_post = JobPostModel.objects.get(id=job_post_id)
        except JobPostModel.DoesNotExist:
            raise serializers.ValidationError(
                detail=f"Job post with ID {data.get('job_post_id')} not found."
            )

        user_company_profile_id = get_user_company_profile_id(request.auth)
        try:
            user_company_profile = UserCompanyProfile.objects.get(
                id=user_company_profile_id
            )
        except UserCompanyProfile.DoesNotExist:
            raise serializers.ValidationError(
                detail=f"User company profile with ID {user_company_profile_id} not found."
            )

        # Get or check existing state
        state = JobPostUserStateModel.objects.filter(
            user_company_profile=user_company_profile, job_post=job_post
        ).first()

        # Activity-specific validation
        if activity_type == ActivityTrackingTypes.SAVE.value:
            if state and state.is_saved:
                raise serializers.ValidationError(
                    {f"{activity_type}": "You have already saved this job post."}
                )

        elif activity_type == ActivityTrackingTypes.UNSAVE.value:
            if not state or not state.is_saved:
                raise serializers.ValidationError(
                    {
                        f"{activity_type}": "You cannot unsave a job post that is not saved."
                    }
                )

        elif activity_type == ActivityTrackingTypes.APPLY.value:
            if state and state.status == "applied":
                raise serializers.ValidationError(
                    {f"{activity_type}": "You have already applied for this job post."}
                )

        # Pass job_post to validated data for later use
        data["job_post"] = job_post

        return data


class BaseJobPostDetailSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(source="job_post.title", read_only=True)
    company = BaseCompanySerializer(source="job_post.company", read_only=True)
    salary_range = BaseDecimalRangeSerializerField(
        source="job_post.salary_range", read_only=True
    )
    salary_currency = serializers.CharField(
        source="job_post.salary_currency", read_only=True
    )
    salary_type = serializers.CharField(source="job_post.salary_type", read_only=True)
    remote_type = serializers.CharField(source="job_post.remote_type", read_only=True)
    time_type = serializers.CharField(source="job_post.time_type", read_only=True)
    job_level = serializers.CharField(source="job_post.job_level", read_only=True)
    location = serializers.CharField(source="job_post.location", read_only=True)
    contract_type = serializers.CharField(
        source="job_post.contract_type", read_only=True
    )
    category = serializers.CharField(source="job_post.category", read_only=True)
    status = serializers.CharField(source="job_post.status", read_only=True)
    apply_count = serializers.IntegerField(read_only=True)
    post_date = serializers.DateField(source="job_post.post_date", read_only=True)
    expire_date = serializers.DateField(source="job_post.expire_date", read_only=True)
    job_description = serializers.CharField(
        source="job_post.job_description", read_only=True
    )
    priority = serializers.CharField(source="job_post.priority", read_only=True)

    class Meta:
        abstract = True


@datetime_format_decorator(
    fields=["save_at", "post_date"],
)
class SavedJobPostReadSerializer(BaseJobPostDetailSerializer):
    post_date = serializers.DateTimeField(source="job_post.post_date", read_only=True)
    expire_date = serializers.DateField(source="job_post.expire_date", read_only=True)

    class Meta(BaseJobPostDetailSerializer.Meta):
        model = JobPostUserStateModel
        fields = [
            "id",
            "job_post_id",
            "job_title",
            "company",
            "salary_range",
            "salary_currency",
            "salary_type",
            "remote_type",
            "time_type",
            "job_level",
            "location",
            "contract_type",
            "category",
            "status",
            "apply_count",
            "is_saved",
            "save_at",
            "post_date",
            "expire_date",
            "job_description",
            "priority",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
        }


@datetime_format_decorator(
    fields=["applied_at", "post_date"],
)
class ApplyJobPostReadSerializer(BaseJobPostDetailSerializer):
    post_date = serializers.DateTimeField(source="job_post.post_date", read_only=True)
    expire_date = serializers.DateField(source="job_post.expire_date", read_only=True)

    class Meta(BaseJobPostDetailSerializer.Meta):
        model = JobPostUserStateModel
        fields = [
            "id",
            "job_post_id",
            "job_title",
            "company",
            "salary_range",
            "salary_currency",
            "salary_type",
            "remote_type",
            "time_type",
            "job_level",
            "location",
            "contract_type",
            "category",
            "status",
            "apply_count",
            "applied_at",
            "post_date",
            "expire_date",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
        }