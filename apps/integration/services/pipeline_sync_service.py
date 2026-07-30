import logging

import requests as http_client
from django.conf import settings

from apps.integration.constants import ConnectorStatus
from apps.integration.models.job_platform import IntegrationPartner, IntegrationUserMapping

logger = logging.getLogger(__name__)


class PipelineSyncService:
    """
    Pushes a pipeline step/status change on a ConnectJob application to the
    connected ERP (Wing Digital) so both systems stay in sync.

    Called asynchronously via Celery after update_pipeline() commits.
    Failures are logged but never raise — they must not affect the recruiter's UX.
    """

    @staticmethod
    def sync_to_erp(application) -> None:
        """
        application: JobApplicationModel (pre-fetched with job_post + profile)
        """
        company_id = str(application.job_post.company_id)

        partner = IntegrationPartner.objects.filter(
            organization_id=company_id,
            status=ConnectorStatus.ACTIVE,
        ).first()

        if not partner:
            logger.debug(
                "PipelineSync: no active integration for company_id=%s — skipped",
                company_id,
            )
            return

        payload = PipelineSyncService._build_payload(application, partner)

        try:
            erp_base = (partner.erp_domain or settings.CONNECTOR_INTEGRATION_URL).rstrip("/")
            response = http_client.patch(
                f"{erp_base}/api/connector-integration/applications/{application.id}/pipeline",
                json=payload,
                headers={"X-CONNECTOR-KEY": partner.partner_inbound_key},
                timeout=15,
            )
        except Exception as exc:
            logger.warning(
                "PipelineSync: HTTP error application_id=%s error=%s",
                application.id,
                exc,
            )
            raise  # re-raise so Celery retries

        if response.status_code not in (200, 201, 204):
            logger.warning(
                "PipelineSync: ERP rejected application_id=%s status=%s body=%s",
                application.id,
                response.status_code,
                response.text[:300],
            )
            response.raise_for_status()

        logger.info(
            "PipelineSync: synced application_id=%s step=%s status=%s",
            application.id,
            application.pipeline_step_name,
            application.pipeline_status_name,
        )

    @staticmethod
    def _build_payload(application, partner) -> dict:
        job_post = application.job_post

        # Resolve WingDigital's own applicant ID if we stored it during the
        # initial sync (ApplicantSyncService stores this in IntegrationUserMapping)
        partner_user_id = None
        if application.profile_id:
            mapping = IntegrationUserMapping.objects.filter(
                connection=partner,
                local_user_id=str(application.profile_id),
            ).first()
            partner_user_id = mapping.partner_user_id if mapping else None

        return {
            # ── Application identifiers ───────────────────────────────────────
            "application_id": str(application.id),
            "application_code": application.code,
            # ERP's own applicant ID (allows WingDigital to match without searching)
            "partner_user_id": partner_user_id,

            # ── Job context ───────────────────────────────────────────────────
            "job_code": job_post.job_code,
            "job_title": job_post.title,
            "tenant_code": job_post.tenant_code or partner.partner_tenant_id,

            # ── New pipeline position ─────────────────────────────────────────
            "pipeline_step": application.pipeline_step_name,
            "pipeline_step_order": application.pipeline_step_order,
            "pipeline_status": application.pipeline_status_name,
            "pipeline_status_order": application.pipeline_status_order,
        }
