from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from django.db import models

from apps.auth_totp_mail.constants.invite_type_contants import InvitationStatus
from apps.auth_totp_mail.models.invitation_models import Invitation
from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.views.base_views import (
    BaseListAPIView,
)
from apps.job_management_app.models.job_application_model import JobApplicationModel
from apps.job_management_app.services.job_application_services import JobApplicationServices
from apps.recruiter_management.serializers.recruiter_schedule_serializer import (
    InvitationScheduleByApplicationListSerializer,
    RecruiterInvitationScheduleListSerializer,
)
from apps.auth_oauth.constants.auth_constants import GroupTypes


class RecruiterInvitationScheduleListView(PermissionMixin, BaseListAPIView):
    serializer_class = RecruiterInvitationScheduleListSerializer
    permission_classes = [IsAuthenticated]

    search_fields = [
        "job_application__applicant_name",
        "job_application__email",
        "job_application__phone_number",
        "job_application__job_post__title",
        "invitation_type",
        "status",
    ]

    filterset_fields = {
        "invitation_type": ["exact"],
        "status": ["exact"],
        "invited_at": ["date", "gte", "lte"],
        "job_application__applicant_name": ["exact", "icontains"],
        "job_application__email": ["exact"],
        "job_application__phone_number": ["exact"],
        "job_application__job_post__title": ["exact", "icontains"],
    }

    ordering_fields = [
        "invited_at",
        "invitation_type",
        "status",
        "job_application__applicant_name",
        "job_application__job_post__title",
    ]
    ordering = ["invited_at"]
    permission_codename = ["recruiter_applicant", "admin_recruiter_applicant"]

    def get_queryset(self):
        now = timezone.now()
        ucp_id = getattr(self.request, "user_company_profile_id", None)
        user = self.request

        qs = (
            Invitation.objects.filter(
                invited_at__gte=now,  # only upcoming + non-expired
                status__in=[
                    InvitationStatus.SENT,
                ],
                job_application__isnull=False,
                job_application__job_post__isnull=False,
                job_application__job_post__deleted_at__isnull=True,
            )
            .select_related(
                "job_application",
                "job_application__job_post",
            )
            # Upcoming first, then by nearest date
            .order_by("invited_at")
        )

        if user.user_type == GroupTypes.ADMIN_RECRUITER:
            return qs.filter(
                job_application__job_post__company_id=self.request.company_id
            )
        elif user.user_type == GroupTypes.RECRUITER:
            if not ucp_id:
                return qs.none()
            return (
                qs.filter(
                    job_application__job_post__company_id=self.request.company_id,
                )
                .filter(JobApplicationServices.recruiter_scope_for_invitation_query(ucp_id))
                .distinct()
            )

        return qs.none()


class InvitationScheduleByApplicationView(BaseListAPIView):
    serializer_class = InvitationScheduleByApplicationListSerializer

    filterset_fields = {
        "invitation_type": ["exact"],
        "status": ["exact"],
        "invited_at": ["date", "gte", "lte"],
    }

    ordering_fields = [
        "invited_at",
        "invitation_type",
        "status",
    ]
    ordering = ["-invited_at"]
    permission_codename = ["recruiter_applicant", "admin_recruiter_applicant"]

    def get_queryset(self):
        job_application_id = self.kwargs["job_application_id"]
        pipeline_config_id = self.kwargs["pipeline_config_id"]
        pipeline_step_id = self.kwargs["pipeline_step_id"]

        # Validate job_application belongs to the company
        get_object_or_404(
            JobApplicationModel,
            id=job_application_id,
            job_post__company_id=self.request.user.company_id,
        )

        return (
            Invitation.objects.filter(
                job_application_id=job_application_id,
                pipeline_config_id=pipeline_config_id,
                pipeline_step_id=pipeline_step_id,
            )
            .select_related(
                "job_application",
                "job_application__job_post",
            )
            .order_by("-invited_at")
        )
