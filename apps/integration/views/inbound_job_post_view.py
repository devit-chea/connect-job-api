import logging

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.base.models.company_model import Company
from apps.integration.constants import ConnectorStatus
from apps.integration.models.job_platform import IntegrationPartner
from apps.integration.serializers.inbound_job_post_serializer import (
    InboundJobPostSerializer,
)
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
      4. Create JobPostModel linked to the partner's company.
      5. Sync to Elasticsearch (best-effort, never blocks the response).
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
        serializer.is_valid(raise_exception=True)
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
            return Response(
                {"status": "error", "message": "Company not found for this integration."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # ── Step 5: Create job post ───────────────────────────────────────────
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
            )

        logger.info(
            "IntegrationJobPost: created job_post_id=%s company_id=%s title=%s",
            job_post.id,
            company.id,
            job_post.title,
        )

        # ── Step 6: Elasticsearch sync (best-effort) ──────────────────────────
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

        return Response(
            {
                "status": "success",
                "message": "Job posted successfully.",
                "job_post_id": str(job_post.id),
            },
            status=status.HTTP_201_CREATED,
        )
