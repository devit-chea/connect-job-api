from django.utils import timezone
from rest_framework import viewsets, permissions
from rest_framework.permissions import AllowAny

from apps.activity_tracking_app.models.job_post_user_activity_count_model import (
    JobPostUserActivityCountModel,
)
from apps.activity_tracking_app.models.job_post_user_state_model import (
    JobPostUserStateModel,
)
from apps.activity_tracking_app.serializers.activity_count_serializer import (
    JobPostUserActivityCountSerializer,
)
from apps.activity_tracking_app.serializers.job_post_activity_serializer import (
    SavedJobPostReadSerializer,
    ApplyJobPostReadSerializer,
)
from apps.base.utils.auth_utils import get_user_company_profile_id


class JobPostUserActivityCountView(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]

    queryset = JobPostUserActivityCountModel.objects.select_related("job_post")
    serializer_class = JobPostUserActivityCountSerializer
    lookup_field = "job_post_id"

    def get_queryset(self):
        return self.queryset.all()


class SavedJobViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Returns only saved jobs for the current user.
    """

    serializer_class = SavedJobPostReadSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "job_post_id"

    def get_queryset(self):
        today = timezone.localdate()
        ucp_id = get_user_company_profile_id(self.request.auth)
        return (
            JobPostUserStateModel.objects.with_apply_count()
            .filter(
                user_company_profile_id=ucp_id,
                is_saved=True,
                job_post__expire_date__gte=today,
            )
            .select_related("job_post")
            .order_by("-save_at")
        )


class AppliedJobViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Returns only applied jobs for the current user.
    """

    serializer_class = ApplyJobPostReadSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "job_post_id"

    def get_queryset(self):
        ucp_id = get_user_company_profile_id(self.request.auth)
        return (
            JobPostUserStateModel.objects.with_apply_count()
            .filter(user_company_profile_id=ucp_id, status="applied")
            .select_related("job_post")
        )
