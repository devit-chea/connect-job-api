import logging
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.auth_totp_mail.models.invitation_models import Invitation
from apps.auth_totp_mail.serializers.applicant_invitation_serializer import (
    ApplicationInvitationSummarySerializer,
    InvitationListQuerySerializer,
)
from apps.auth_totp_mail.services.application_invitation_service import (
    ApplicantInvitationService,
)
from apps.base.views.base_views import BaseModelViewSet
from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.mixins.custom_jwt_request_mixin import CustomJWTRequestMixin
from apps.job_management_app.models.job_application_model import JobApplicationModel

logger = logging.getLogger(__name__)


class JobApplicationInvitationViewSet(PermissionMixin, BaseModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get"]  # only GET allowed
    permission_codename = [
        "applicant_manage_profile",
    ]
    serializer_class = ApplicationInvitationSummarySerializer

    def get_serializer_class(self):
        return ApplicationInvitationSummarySerializer

    def get_queryset(self):
        return Invitation.objects.none()  # required by BaseModelViewSet

    def _get_job_application(self, request, job_application_id):
        user_company_profile_id = getattr(request, "user_company_profile_id", None)
        if not user_company_profile_id:
            return None, Response(
                {"detail": "This invitation is not belong to you."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            job_application = JobApplicationModel.objects.get(
                id=job_application_id,
                create_ucp_id=user_company_profile_id,
            )
        except JobApplicationModel.DoesNotExist:
            return None, Response(
                {"detail": "Job application not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return job_application, None

    def _build_entries(self, all_invitations: list) -> list:
        """Group invitations into parent+subs entries."""

        def collect_subs(root_id, invs):
            subs = []
            children = sorted(
                [inv for inv in invs if inv.rescheduled_from_id == root_id],
                key=lambda x: x.create_date,
                reverse=False,  # oldest first
            )
            for child in children:
                subs.append(child)
                subs.extend(collect_subs(child.id, invs))
            return subs

        referenced_ids = {
            inv.rescheduled_from_id
            for inv in all_invitations
            if inv.rescheduled_from_id is not None
        }

        entries = []
        visited_ids = set()

        originals = [
            inv
            for inv in all_invitations
            if inv.rescheduled_from_id is None and inv.id in referenced_ids
        ]
        standalones = [
            inv
            for inv in all_invitations
            if inv.rescheduled_from_id is None and inv.id not in referenced_ids
        ]

        for original in originals:
            if original.id in visited_ids:
                continue
            subs = collect_subs(original.id, all_invitations)
            entries.append({"main": original, "subs": subs})
            visited_ids.add(original.id)
            for sub in subs:
                visited_ids.add(sub.id)

        for standalone in standalones:
            if standalone.id in visited_ids:
                continue
            entries.append({"main": standalone, "subs": []})
            visited_ids.add(standalone.id)

        # Sort by main.id ASC
        return sorted(entries, key=lambda x: x["main"].id, reverse=True)

    def _serialize_entries(self, entries: list, all_invitations: list) -> list:
        if not entries:
            return []

        # Build recruiter map from all invitations in one query
        recruiter_map = ApplicantInvitationService.build_recruiter_map(all_invitations)

        latest_entry = entries[0]  # entries sorted DESC, so [0] is the newest
        latest_invitation_id = latest_entry["main"].id
        latest_sub_id = latest_entry["subs"][-1].id if latest_entry["subs"] else None

        result = []
        for entry in entries:
            serialized = ApplicationInvitationSummarySerializer(
                entry["main"],
                context={
                    "latest_invitation_id": latest_invitation_id,
                    "latest_sub_id": latest_sub_id,
                    "subs": entry["subs"],
                    "recruiter_map": recruiter_map,  # inject
                },
            ).data
            result.append(serialized)

        return result

    def list(self, request, job_application_id=None):
        job_application, error = self._get_job_application(request, job_application_id)
        if error:
            return error

        query_serializer = InvitationListQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        all_invitations = list(
            Invitation.objects.filter(
                job_application_id=job_application.id,
                pipeline_step_id=query_serializer.validated_data["pipeline_step_id"],
                pipeline_config_id=query_serializer.validated_data[
                    "pipeline_config_id"
                ],
            )
            .select_related("mail_template")
            .order_by("-create_date")
        )

        entries = self._build_entries(all_invitations)

        page = self.paginate_queryset(entries)
        if page is not None:
            serialized = self._serialize_entries(page, all_invitations)
            return self.get_paginated_response(serialized)

        serialized = self._serialize_entries(entries, all_invitations)
        return Response(serialized, status=status.HTTP_200_OK)

    def retrieve(self, request, job_application_id=None, pk=None):
        job_application, error = self._get_job_application(request, job_application_id)
        if error:
            return error

        user_company_profile_id = getattr(request, "user_company_profile_id", None)

        try:
            main = Invitation.objects.select_related("mail_template").get(
                id=pk,
                job_application_id=job_application.id,
                job_application__create_ucp_id=user_company_profile_id,
            )
        except Invitation.DoesNotExist:
            return Response(
                {"detail": "Invitation not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        all_invitations = list(
            Invitation.objects.filter(
                job_application_id=job_application.id,
                pipeline_step_id=main.pipeline_step_id,
                pipeline_config_id=main.pipeline_config_id,
            )
            .select_related("mail_template")
            .order_by("-create_date")
        )

        entries = self._build_entries(all_invitations)
        recruiter_map = ApplicantInvitationService.build_recruiter_map(all_invitations)

        entry = next(
            (e for e in entries if e["main"].id == main.id),
            next(
                (e for e in entries if any(s.id == main.id for s in e["subs"])),
                {"main": main, "subs": []},
            ),
        )

        subs = entry["subs"]
        latest_sub_id = subs[-1].id if subs else None

        serialized = ApplicationInvitationSummarySerializer(
            entry["main"],
            context={
                "latest_invitation_id": entry["main"].id,
                "latest_sub_id": latest_sub_id,
                "subs": subs,
                "recruiter_map": recruiter_map,
            },
        ).data

        return Response(serialized, status=status.HTTP_200_OK)
