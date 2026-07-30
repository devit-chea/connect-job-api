import logging

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.integration.constants import ConnectorStatus
from apps.integration.models.job_platform import IntegrationPartner, IntegrationSyncLog, SyncLogType, SyncLogStatus
from apps.integration.serializers.inbound_pipeline_serializer import InboundPipelineSerializer
from apps.integration.utils.crypto_utils import hash_sha256
from apps.job_management_app.models.job_application_model import JobApplicationModel
from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineConfigStepModel,
    JobPipelineStatusConfigModel,
)
from apps.job_management_app.services.job_application_services import JobApplicationServices

logger = logging.getLogger(__name__)


class InboundPipelineUpdateView(APIView):
    """
    PATCH /api/v1/integration/applications/{application_id}/pipeline

    Called server-to-server by the Connect ERP when an applicant's pipeline
    step/status changes on the ERP side.

    Auth: X-CONNECTOR-KEY header (Key_Beta / partner_outbound_key).

    Loop prevention: passes skip_erp_sync=True to update_pipeline() so the
    normal on_commit ERP sync task is NOT queued, breaking the infinite loop.
    """

    permission_classes = [AllowAny]

    def _authenticate_partner(self, request):
        connector_key = request.headers.get("X-CONNECTOR-KEY")
        if not connector_key:
            return None, Response(
                {"status": "error", "message": "Missing X-CONNECTOR-KEY header."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        partner = IntegrationPartner.objects.filter(
            partner_outbound_hash=hash_sha256(connector_key),
            status=ConnectorStatus.ACTIVE,
        ).first()

        if not partner:
            return None, Response(
                {"status": "error", "message": "Invalid or inactive connector key."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return partner, None

    def patch(self, request, application_id):
        # ── Auth ─────────────────────────────────────────────────────────────
        partner, error = self._authenticate_partner(request)
        if error:
            return error

        # ── Validate payload ─────────────────────────────────────────────────
        serializer = InboundPipelineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        step_name = data["pipeline_step"]
        status_name = data["pipeline_status"]
        step_order = data.get("pipeline_step_order")
        status_order = data.get("pipeline_status_order")

        # ── Resolve application ───────────────────────────────────────────────
        application = (
            JobApplicationModel.objects
            .select_related("job_post", "pipeline_config", "pipeline_step", "pipeline_status")
            .filter(id=application_id, is_deleted=False)
            .first()
        )

        if not application:
            # Try lookup by code (ERP may send the code instead of UUID)
            application = (
                JobApplicationModel.objects
                .select_related("job_post", "pipeline_config", "pipeline_step", "pipeline_status")
                .filter(code=application_id, is_deleted=False)
                .first()
            )

        if not application:
            return Response(
                {"status": "error", "message": f"Application '{application_id}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Ensure the application belongs to this partner's company
        if str(application.job_post.company_id) != partner.organization_id:
            return Response(
                {"status": "error", "message": "Application does not belong to this integration partner."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── Resolve pipeline status ────────────────────────────────────────────
        # First try matching by name within the application's pipeline config
        pipeline_config = application.pipeline_config
        status_qs = JobPipelineStatusConfigModel.objects.filter(
            name=status_name,
            is_active=True,
        )
        if pipeline_config:
            # Try scoped to this pipeline config first
            scoped = status_qs.filter(
                step__pipeline_config=pipeline_config
            )
            if status_order is not None:
                scoped = scoped.filter(order=status_order)
            pipeline_status_obj = scoped.first() or status_qs.first()
        else:
            if status_order is not None:
                status_qs = status_qs.filter(order=status_order)
            pipeline_status_obj = status_qs.first()

        if not pipeline_status_obj:
            return Response(
                {"status": "error", "message": f"Pipeline status '{status_name}' not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Call update_pipeline with skip_erp_sync=True ─────────────────────
        try:
            updated_app = JobApplicationServices.update_pipeline(
                job_post_id=application.job_post_id,
                application_id=application.id,
                status=pipeline_status_obj,
                actor=None,
                actor_profile_id=None,
                skip_erp_sync=True,
            )
        except JobApplicationModel.DoesNotExist:
            return Response(
                {"status": "error", "message": "Application not found during pipeline update."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as exc:
            logger.error(
                "InboundPipelineUpdate: failed application_id=%s error=%s",
                application_id,
                exc,
                exc_info=True,
            )
            try:
                IntegrationSyncLog.objects.create(
                    partner=partner,
                    sync_type=SyncLogType.PIPELINE_INBOUND,
                    status=SyncLogStatus.FAILED,
                    reference_id=str(application_id),
                    payload=request.data,
                    error_message=str(exc),
                )
            except Exception:
                pass
            return Response(
                {"status": "error", "message": "Pipeline update failed.", "details": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info(
            "InboundPipelineUpdate: SUCCESS application_id=%s step=%s status=%s",
            updated_app.id,
            updated_app.pipeline_step_name,
            updated_app.pipeline_status_name,
        )

        return Response(
            {
                "status": "success",
                "message": "Pipeline updated successfully.",
                "application_id": str(updated_app.id),
                "pipeline_step": updated_app.pipeline_step_name,
                "pipeline_status": updated_app.pipeline_status_name,
            },
            status=status.HTTP_200_OK,
        )
