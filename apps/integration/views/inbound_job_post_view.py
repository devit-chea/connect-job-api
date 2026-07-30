import logging

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.base.models.company_model import Company
from apps.integration.constants import ConnectorStatus
from apps.integration.models.job_platform import IntegrationPartner, IntegrationUserMapping
from apps.integration.serializers.inbound_job_post_serializer import (
    InboundJobPostSerializer,
)
from apps.integration.models.job_platform import IntegrationSyncLog, SyncLogType, SyncLogStatus
from apps.integration.utils.crypto_utils import hash_sha256
from apps.integration.utils.mapping_utils import transform_erp_payload
from apps.job_management_app.constants.job_post_types import JobPostStatusTypes
from apps.job_management_app.models.job_post_model import JobPostModel

logger = logging.getLogger(__name__)


class IntegrationJobPostView(APIView):
    """
    POST /api/v1/integration/jobs/publish

    Called by Wing Digital (ERP) to create a job vacancy on ConnectJob.
    Auth: X-CONNECTOR-KEY header carrying Key_Beta (partner_outbound_key).

    Flow:
      1. Validate X-CONNECTOR-KEY → resolve IntegrationPartner.
      2. transform_erp_payload() maps ERP field names → ConnectJob field names
         and translates enum values using configured IntegrationValueMappings.
      3. Validate the mapped payload with InboundJobPostSerializer.
      4. Resolve `created_by` (ERP's own user id) to a UserCompanyProfile via
         IntegrationUserMapping, so the job post is attributed to the same
         ConnectJob recruiter as its ERP creator. Falls back to unattributed
         (create_ucp_id/create_uid left null) when missing or unmatched —
         never blocks job publishing over an identity mismatch.
      5. Create JobPostModel linked to the partner's company.
      6. Sync to Elasticsearch (best-effort, never blocks the response).
    """

    permission_classes = [AllowAny]

    def _authenticate_partner(self, request):
        connector_key = request.headers.get("X-CONNECTOR-KEY")
        if not connector_key:
            return None, Response(
                {"status": "error", "message": "Missing X-CONNECTOR-KEY header."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        incoming_hash = hash_sha256(connector_key)
        partner = (
            IntegrationPartner.objects.filter(
                partner_outbound_hash=incoming_hash,
                status=ConnectorStatus.ACTIVE,
            )
            .select_related("company")
            .first()
        )

        if not partner:
            return None, Response(
                {"status": "error", "message": "Invalid or inactive connector key."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return partner, None

    @staticmethod
    def _log_failure(partner, payload: dict, error_message: str, reference_id: str = None):
        """Write an IntegrationSyncLog entry so operators can review and retry."""
        try:
            IntegrationSyncLog.objects.create(
                partner=partner,
                sync_type=SyncLogType.JOB_POST_INBOUND,
                status=SyncLogStatus.FAILED,
                reference_id=reference_id,
                payload=payload,
                error_message=error_message,
            )
        except Exception as log_exc:
            logger.warning("IntegrationJobPost: could not write sync log error=%s", log_exc)

    def post(self, request):
        partner, error = self._authenticate_partner(request)
        if error:
            return error

        # ── Step 1: Transform ERP payload → ConnectJob field names + values ──
        mapped_data = transform_erp_payload(str(partner.id), request.data)

        logger.info(
            "IntegrationJobPost: partner_id=%s original_keys=%s mapped_keys=%s",
            partner.id,
            list(request.data.keys()),
            list(mapped_data.keys()),
        )

        # ── Step 2: Validate mapped data ─────────────────────────────────────
        serializer = InboundJobPostSerializer(data=mapped_data)
        if not serializer.is_valid():
            self._log_failure(
                partner,
                payload=request.data,
                error_message=str(serializer.errors),
                reference_id=str(request.data.get("job_code") or ""),
            )
            return Response(
                {"status": "error", "message": "Payload validation failed.", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = dict(serializer.validated_data)

        # ── Step 3: Extract salary_min / salary_max → DecimalRangeField ──────
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
                logger.warning(
                    "IntegrationJobPost: failed to build salary_range "
                    "salary_min=%s salary_max=%s",
                    salary_min,
                    salary_max,
                )

        # ── Step 4: Resolve company ───────────────────────────────────────────
        company = Company.objects.filter(id=partner.organization_id).first()
        if not company:
            self._log_failure(
                partner,
                payload=request.data,
                error_message="Company not found for this integration partner.",
                reference_id=str(request.data.get("job_code") or ""),
            )
            return Response(
                {"status": "error", "message": "Company not found for this integration."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # ── Step 5: Resolve actor — attribute the job post to the ERP creator ──
        # `created_by` is an identity reference (ERP's own user id), not a job
        # attribute, so it's read directly from the raw payload rather than
        # going through transform_erp_payload()'s field/value mapping.
        create_ucp_id = None
        create_uid = None
        erp_actor_id = request.data.get("created_by")
        if erp_actor_id:
            actor_mapping = (
                IntegrationUserMapping.objects
                .filter(connection=partner, partner_user_id=str(erp_actor_id))
                .select_related("user_company_profile")
                .first()
            )
            if actor_mapping and actor_mapping.user_company_profile_id:
                create_ucp_id = actor_mapping.user_company_profile_id
                create_uid = actor_mapping.user_company_profile.profile_id
            else:
                logger.info(
                    "IntegrationJobPost: created_by=%s has no matching "
                    "IntegrationUserMapping for partner_id=%s — job post will "
                    "be created unattributed",
                    erp_actor_id, partner.id,
                )

        # ── Step 6: Create job post ───────────────────────────────────────────
        job_post_status = data.pop("status", None) or JobPostStatusTypes.ACTIVE

        # Fall back to partner's ERP tenant ID if ERP didn't send tenant_code
        if not data.get("tenant_code"):
            data["tenant_code"] = partner.partner_tenant_id

        with transaction.atomic():
            job_post = JobPostModel.objects.create(
                **data,
                salary_range=salary_range,
                company=company,
                status=job_post_status,
                is_active=True,
                create_ucp_id=create_ucp_id,
                create_uid=create_uid,
            )

        logger.info(
            "IntegrationJobPost: created job_post_id=%s company_id=%s title=%s "
            "create_ucp_id=%s",
            job_post.id,
            company.id,
            job_post.title,
            create_ucp_id,
        )

        # ── Step 7: Elasticsearch sync (best-effort) ──────────────────────────
        try:
            from apps.elasticsearch_app.services.job_post_es_sync_services import (
                JobPostESSyncServices,
            )
            JobPostESSyncServices.sync(job_post)
        except Exception as exc:
            logger.warning(
                "IntegrationJobPost: ES sync failed job_post_id=%s error=%s",
                job_post.id,
                exc,
            )

        # ── Step 8: Write success log ─────────────────────────────────────────
        try:
            IntegrationSyncLog.objects.create(
                partner=partner,
                sync_type=SyncLogType.JOB_POST_INBOUND,
                status=SyncLogStatus.SUCCESS,
                reference_id=str(job_post.id),
                payload=request.data,
            )
        except Exception:
            pass  # Never let logging break the success response

        return Response(
            {
                "status": "success",
                "message": "Job posted successfully.",
                "job_post_id": str(job_post.id),
            },
            status=status.HTTP_201_CREATED,
        )
