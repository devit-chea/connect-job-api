from rest_framework import serializers

from apps.activity_tracking_app.constants.job_activity_types import (
    ActivityTrackingTypes,
)
from apps.activity_tracking_app.models.job_post_user_state_model import (
    JobPostUserStateModel,
)
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.base.utils.auth_utils import get_user_company_profile_id
from apps.job_management_app.models.job_post_model import JobPostModel


class JobPostSaveUnsaveWriteSerializer(serializers.Serializer):
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
                    detail="You have already saved this job post."
                )

        elif activity_type == ActivityTrackingTypes.UNSAVE.value:
            if not state or not state.is_saved:
                raise serializers.ValidationError(
                    detail="You cannot unsave a job post that is not saved."
                )

        # Pass job_post to validated data for later use
        data["job_post"] = job_post

        return data
