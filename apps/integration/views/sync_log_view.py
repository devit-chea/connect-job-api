import logging

from django.utils import timezone
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.base.mixins.custom_jwt_request_mixin import CustomJWTRequestMixin
from apps.base.mixins.permission_mixin import PermissionMixin
from apps.integration.models.job_platform import (
    IntegrationSyncLog,
    SyncLogStatus,
    SyncLogType,
)

logger = logging.getLogger(__name__)


# ── Serializers ───────────────────────────────────────────────────────────────

class SyncLogSerializer(drf_serializers.ModelSerializer):
    partner_id = drf_serializers.UUIDField(source="partner.id", read_only=True, allow_null=True)

    class Meta:
        model = IntegrationSyncLog
        fields = [
            "id", "partner_id", "sync_type", "status",
            "reference_id", "error_message", "retry_count",
            "created_at", "last_attempted_at",
        ]


class SyncLogDetailSerializer(SyncLogSerializer):
    class Meta(SyncLogSerializer.Meta):
        fields = SyncLogSerializer.Meta.fields + ["payload"]


# ── Views ─────────────────────────────────────────────────────────────────────

class IntegrationSyncLogListView(PermissionMixin, CustomJWTRequestMixin, APIView):
    """
    GET /api/v1/integration/sync-logs

    Lists all sync failures for the calling operator. Supports query filters:
      ?sync_type=job_post_inbound|pipeline_outbound|applicant_outbound|pipeline_inbound
      ?status=failed|retrying|success
      ?partner_id=<uuid>
    """

    permission_classes = [IsAuthenticated]
    permission_codename = "operator_manage_company"

    def get(self, request):
        qs = IntegrationSyncLog.objects.select_related("partner").all()

        sync_type = request.query_params.get("sync_type")
        if sync_type:
            qs = qs.filter(sync_type=sync_type)

        log_status = request.query_params.get("status")
        if log_status:
            qs = qs.filter(status=log_status)

        partner_id = request.query_params.get("partner_id")
        if partner_id:
            qs = qs.filter(partner_id=partner_id)

        serializer = SyncLogSerializer(qs[:100], many=True)
        return Response({"data": serializer.data, "count": qs.count()})


class IntegrationSyncLogDetailView(PermissionMixin, CustomJWTRequestMixin, APIView):
    """
    GET /api/v1/integration/sync-logs/<id>

    Returns the full sync log including the original payload.
    """

    permission_classes = [IsAuthenticated]
    permission_codename = "operator_manage_company"

    def get(self, request, log_id):
        log = IntegrationSyncLog.objects.select_related("partner").filter(id=log_id).first()
        if not log:
            return Response(
                {"status": "error", "message": "Sync log not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"data": SyncLogDetailSerializer(log).data})


class IntegrationSyncLogRetryView(PermissionMixin, CustomJWTRequestMixin, APIView):
    """
    POST /api/v1/integration/sync-logs/<id>/retry

    Replays the stored payload through the appropriate handler:
      - job_post_inbound     → re-runs inbound job post creation
      - pipeline_outbound    → re-dispatches sync_pipeline_to_erp Celery task
      - applicant_outbound   → re-dispatches sync_applicant_to_erp Celery task
      - pipeline_inbound     → re-calls InboundPipelineUpdateView logic inline
    """

    permission_classes = [IsAuthenticated]
    permission_codename = "operator_manage_company"

    def post(self, request, log_id):
        log = IntegrationSyncLog.objects.select_related("partner").filter(id=log_id).first()
        if not log:
            return Response(
                {"status": "error", "message": "Sync log not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if log.status == SyncLogStatus.SUCCESS:
            return Response(
                {"status": "error", "message": "This entry already succeeded — no retry needed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        log.status = SyncLogStatus.RETRYING
        log.retry_count += 1
        log.last_attempted_at = timezone.now()
        log.save(update_fields=["status", "retry_count", "last_attempted_at"])

        try:
            result_message = self._dispatch(log)
            log.status = SyncLogStatus.SUCCESS
            log.error_message = ""
            log.save(update_fields=["status", "error_message"])
            return Response({"status": "success", "message": result_message})
        except Exception as exc:
            log.status = SyncLogStatus.FAILED
            log.error_message = str(exc)
            log.save(update_fields=["status", "error_message"])
            logger.error("SyncLogRetry: failed log_id=%s error=%s", log_id, exc, exc_info=True)
            return Response(
                {"status": "error", "message": "Retry failed.", "details": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _dispatch(self, log: IntegrationSyncLog) -> str:
        if log.sync_type == SyncLogType.JOB_POST_INBOUND:
            return self._retry_job_post(log)
        if log.sync_type == SyncLogType.PIPELINE_OUTBOUND:
            return self._retry_pipeline_outbound(log)
        if log.sync_type == SyncLogType.APPLICANT_OUTBOUND:
            return self._retry_applicant_outbound(log)
        if log.sync_type == SyncLogType.PIPELINE_INBOUND:
            return self._retry_pipeline_inbound(log)
        raise ValueError(f"Unknown sync_type: {log.sync_type}")

    @staticmethod
    def _retry_job_post(log: IntegrationSyncLog) -> str:
        """Re-run inbound job post creation using the stored raw ERP payload."""
        from apps.base.models.company_model import Company
        from apps.integration.models.job_platform import IntegrationSyncLog as SL
        from apps.integration.utils.mapping_utils import transform_erp_payload
        from apps.integration.serializers.inbound_job_post_serializer import InboundJobPostSerializer
        from apps.job_management_app.constants.job_post_types import JobPostStatusTypes
        from apps.job_management_app.models.job_post_model import JobPostModel

        partner = log.partner
        if not partner:
            raise ValueError("No partner linked to this log entry.")

        mapped_data = transform_erp_payload(str(partner.id), log.payload)
        serializer = InboundJobPostSerializer(data=mapped_data)
        if not serializer.is_valid():
            raise ValueError(f"Validation failed: {serializer.errors}")

        data = dict(serializer.validated_data)
        salary_min = data.pop("salary_min", None)
        salary_max = data.pop("salary_max", None)
        salary_range = None
        if salary_min is not None or salary_max is not None:
            try:
                from psycopg.types.range import NumericRange
                salary_range = NumericRange(
                    lower=float(salary_min) if salary_min is not None else None,
                    upper=float(salary_max) if salary_max is not None else None,
                    bounds="[)",
                )
            except Exception:
                pass

        company = Company.objects.filter(id=partner.organization_id).first()
        if not company:
            raise ValueError("Company not found for this integration partner.")

        job_post_status = data.pop("status", None) or JobPostStatusTypes.ACTIVE
        if not data.get("tenant_code"):
            data["tenant_code"] = partner.partner_tenant_id

        from django.db import transaction
        with transaction.atomic():
            job_post = JobPostModel.objects.create(
                **data,
                salary_range=salary_range,
                company=company,
                status=job_post_status,
                is_active=True,
            )

        return f"Job post created successfully (job_post_id={job_post.id})."

    @staticmethod
    def _retry_pipeline_outbound(log: IntegrationSyncLog) -> str:
        """Re-dispatch the pipeline ERP sync Celery task."""
        from apps.integration.tasks import sync_pipeline_to_erp

        application_id = log.reference_id
        if not application_id:
            raise ValueError("reference_id (application_id) is missing from the log entry.")

        sync_pipeline_to_erp.delay(application_id)
        return f"Pipeline sync re-queued for application_id={application_id}."

    @staticmethod
    def _retry_applicant_outbound(log: IntegrationSyncLog) -> str:
        """Re-dispatch the applicant ERP sync Celery task."""
        from apps.integration.tasks import sync_applicant_to_erp

        application_id = log.reference_id
        if not application_id:
            raise ValueError("reference_id (application_id) is missing from the log entry.")

        sync_applicant_to_erp.delay(application_id)
        return f"Applicant sync re-queued for application_id={application_id}."

    @staticmethod
    def _retry_pipeline_inbound(log: IntegrationSyncLog) -> str:
        """Re-apply the stored ERP pipeline update payload to ConnectJob."""
        from apps.job_management_app.models.job_application_model import JobApplicationModel
        from apps.job_management_app.models.job_pipeline_config_model import JobPipelineStatusConfigModel
        from apps.job_management_app.services.job_application_services import JobApplicationServices

        application_id = log.reference_id
        payload = log.payload
        status_name = payload.get("pipeline_status") or payload.get("pipeline_step")

        application = (
            JobApplicationModel.objects
            .select_related("job_post", "pipeline_config", "pipeline_step", "pipeline_status")
            .filter(id=application_id, is_deleted=False)
            .first()
        )
        if not application:
            raise ValueError(f"Application {application_id} not found.")

        pipeline_status_obj = JobPipelineStatusConfigModel.objects.filter(
            name=status_name, is_active=True
        ).first()
        if not pipeline_status_obj:
            raise ValueError(f"Pipeline status '{status_name}' not found.")

        JobApplicationServices.update_pipeline(
            job_post_id=application.job_post_id,
            application_id=application.id,
            status=pipeline_status_obj,
            actor=None,
            actor_profile_id=None,
            skip_erp_sync=True,
        )
        return f"Inbound pipeline update re-applied for application_id={application_id}."
