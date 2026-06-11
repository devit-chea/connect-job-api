import logging
from rest_framework import status, viewsets, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.auth_oauth.services.user_company_profile_service import (
    UserCompanyProfileService,
)
from apps.auth_totp_mail.constants.invite_type_contants import InvitationStatus
from apps.auth_totp_mail.models.invitation_models import Invitation
from apps.auth_totp_mail.serializers.invitation_serializer import (
    InvitationHistoryQuerySerializer,
    InvitationHistoryResponseSerializer,
    InvitationResponseSerializer,
    RescheduleInvitationSerializer,
    SendInvitationSerializer,
    UpcomingEventQuerySerializer,
    UpcomingEventSerializer,
    UpdateInvitationStatusSerializer,
)
from apps.auth_totp_mail.services.invitation_service import InvitationService
from apps.auth_totp_mail.utils.invitation_utils import INVITATION_NOT_FOUND
from apps.base.mixins.custom_jwt_request_mixin import CustomJWTRequestMixin
from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.views.base_views import BaseModelViewSet
from apps.job_management_app.models.job_application_model import JobApplicationModel

logger = logging.getLogger(__name__)


class SendInvitationView(PermissionMixin, CustomJWTRequestMixin, APIView):
    permission_classes = [IsAuthenticated]
    permission_codename = ["recruiter_applicant", "admin_recruiter_applicant"]

    def post(self, request, *args, **kwargs):
        serializer = SendInvitationSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        company_id = getattr(request, "company_id", None)
        user_company_profile_id = getattr(request, "user_company_profile_id", None)
        ucp = UserCompanyProfileService.get_by_id(user_company_profile_id)

        try:
            invitation = InvitationService.send_invitation(
                validated_data=serializer.validated_data,
                job_application=serializer._job_application,
                mail_template=serializer._mail_template,
                company_id=company_id,
                ucp=ucp,
                pipeline_config=serializer._pipeline_config,
                pipeline_step=serializer._pipeline_step,
            )
        except ValueError as exc:
            # Race condition caught at DB level
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception(exc)
            return Response(
                {"detail": "Failed to send invitation. Please try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_serializer = InvitationResponseSerializer(invitation)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class InvitationHistoryView(PermissionMixin, CustomJWTRequestMixin, APIView):
    permission_classes = [IsAuthenticated]
    permission_codename = ["recruiter_applicant", "admin_recruiter_applicant"]

    def get(self, request, job_application_id, *args, **kwargs):
        # Validate query params
        query_serializer = InvitationHistoryQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        company_id = getattr(request, "company_id", None)

        # Verify job application belongs to this company
        if not JobApplicationModel.objects.filter(id=job_application_id).exists():
            return Response(
                {"detail": "Job application not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        invitations = InvitationService.get_invitation_history(
            job_application_id=job_application_id,
            company_id=company_id,
            filters=query_serializer.validated_data,
        )

        response_serializer = InvitationHistoryResponseSerializer(
            invitations, many=True
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class InvitationDetailView(PermissionMixin, CustomJWTRequestMixin, APIView):
    permission_classes = [IsAuthenticated]
    permission_codename = ["recruiter_applicant", "admin_recruiter_applicant"]

    def get(self, request, invitation_id, *args, **kwargs):
        company_id = getattr(request, "company_id", None)

        try:
            invitation = Invitation.objects.select_related(
                "mail_template", "job_application"
            ).get(id=invitation_id, company_id=company_id)
        except Invitation.DoesNotExist:
            return Response(
                {"detail": INVITATION_NOT_FOUND},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = InvitationHistoryResponseSerializer(invitation)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RescheduleInvitationView(PermissionMixin, CustomJWTRequestMixin, APIView):
    permission_classes = [IsAuthenticated]
    permission_codename = ["recruiter_applicant", "admin_recruiter_applicant"]

    def patch(self, request, invitation_id, *args, **kwargs):
        company_id = getattr(request, "company_id", None)
        user_company_profile_id = getattr(request, "user_company_profile_id", None)
        ucp = UserCompanyProfileService.get_by_id(user_company_profile_id)

        # Fetch and validate ownership
        try:
            invitation = Invitation.objects.select_related(
                "mail_template", "job_application"
            ).get(id=invitation_id, company_id=company_id)
        except Invitation.DoesNotExist:
            return Response(
                {"detail": INVITATION_NOT_FOUND},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Guard against rescheduling already cancelled invitations
        if invitation.status == InvitationStatus.CANCELLED:
            return Response(
                {"detail": "Cannot reschedule a cancelled invitation."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = RescheduleInvitationSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        # Pass resolved template onto validated_data
        if hasattr(serializer, "_mail_template"):
            serializer.validated_data["_mail_template"] = serializer._mail_template

        try:
            invitation = InvitationService.reschedule_invitation(
                invitation=invitation,
                validated_data=serializer.validated_data,
                ucp=ucp,
            )
        except Exception as exc:
            logger.exception(exc)
            return Response(
                {"detail": "Failed to reschedule invitation. Please try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_serializer = InvitationResponseSerializer(invitation)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class UpdateInvitationStatusView(PermissionMixin, CustomJWTRequestMixin, APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, invitation_id, *args, **kwargs):
        company_id = getattr(request, "company_id", None)

        try:
            invitation = Invitation.objects.get(id=invitation_id, company_id=company_id)
        except Invitation.DoesNotExist:
            return Response(
                {"detail": INVITATION_NOT_FOUND},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = UpdateInvitationStatusSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        try:
            invitation = InvitationService.update_invitation_status(
                invitation=invitation,
                validated_data=serializer.validated_data,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_serializer = InvitationHistoryResponseSerializer(invitation)
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class ApplicantUpcomingEventsView(
    PermissionMixin, CustomJWTRequestMixin, viewsets.ReadOnlyModelViewSet
):
    permission_classes = [IsAuthenticated]
    serializer_class = UpcomingEventSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = [
        "invitation_type",
        "job_application__job_post__title",
        "job_application__job_post__company__name",
    ]

    def get_queryset(self):
        user_company_profile_id = getattr(self.request, "user_company_profile_id", None)
        ucp = UserCompanyProfileService.get_by_id(user_company_profile_id)

        query_serializer = UpcomingEventQuerySerializer(data=self.request.query_params)
        query_serializer.is_valid(raise_exception=True)

        return InvitationService.get_upcoming_events(
            ucp=ucp,
            filters=query_serializer.validated_data,
        )
