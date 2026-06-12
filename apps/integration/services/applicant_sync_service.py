import logging

import requests as http_client
from django.conf import settings

from apps.integration.constants import ConnectorStatus
from apps.integration.models.job_platform import IntegrationPartner, IntegrationUserMapping

logger = logging.getLogger(__name__)


class ApplicantSyncService:
    """
    Pushes a new job application to the connected ERP (Wing Digital) so the
    applicant appears in their pipeline automatically.

    Called asynchronously via Celery after JobApplicationModel is created.
    Failures are logged but never raise — they must not break the applicant's
    experience on ConnectJob.
    """

    @staticmethod
    def sync_to_erp(application) -> None:
        """
        application: JobApplicationModel instance (pre-fetched with job_post + profile)
        """
        company_id = str(application.job_post.company_id)

        partner = IntegrationPartner.objects.filter(
            organization_id=company_id,
            status=ConnectorStatus.ACTIVE,
        ).first()

        if not partner:
            logger.debug(
                "ApplicantSync: no active integration for company_id=%s — skipped",
                company_id,
            )
            return

        payload = ApplicantSyncService._build_payload(application, partner)

        try:
            response = http_client.post(
                f"{settings.CONNECTOR_INTEGRATION_URL}"
                f"/api/connector-integration/applicants",
                json=payload,
                headers={"X-CONNECTOR-KEY": partner.partner_inbound_key},
                timeout=15,
            )
        except Exception as exc:
            logger.warning(
                "ApplicantSync: HTTP error application_id=%s error=%s",
                application.id,
                exc,
            )
            raise  # re-raise so Celery can retry

        if response.status_code not in (200, 201):
            logger.warning(
                "ApplicantSync: ERP rejected application_id=%s status=%s body=%s",
                application.id,
                response.status_code,
                response.text[:300],
            )
            response.raise_for_status()  # triggers Celery retry

        # Store the ERP's applicant ID for future cross-reference
        partner_user_id = (
            response.json().get("applicant_id")
            or response.json().get("partner_user_id")
        )
        if partner_user_id and application.profile_id:
            IntegrationUserMapping.objects.update_or_create(
                connection=partner,
                local_user_id=str(application.profile_id),
                defaults={"partner_user_id": str(partner_user_id)},
            )

        logger.info(
            "ApplicantSync: synced application_id=%s → ERP partner_user_id=%s",
            application.id,
            partner_user_id,
        )

    @staticmethod
    def _build_payload(application, partner) -> dict:
        job_post = application.job_post
        profile = application.profile

        payload = {
            # ── Application identifiers ───────────────────────────────────────
            "application_id": str(application.id),
            "application_code": application.code,
            "apply_date": (
                application.apply_date.isoformat() if application.apply_date else None
            ),

            # ── Applicant info ────────────────────────────────────────────────
            "applicant_name": application.applicant_name,
            "email": application.email,
            "phone_number": application.phone_number,
            "current_position": application.applicant_current_position,
            "apply_message": application.apply_message,
            "expected_salary": (
                str(application.expected_salary)
                if application.expected_salary is not None
                else None
            ),

            # ── Attachments (file IDs on ConnectJob storage) ──────────────────
            "cv_file_id": application.cv_file_id,
            "cover_letter_file_id": application.cover_letter_file_id,
            "additional_file_ids": application.additional_file_ids,

            # ── Job post context ──────────────────────────────────────────────
            "job_code": job_post.job_code,
            "job_title": job_post.title,
            # Fall back to ERP's own tenant ID so it can look up the vacancy
            "tenant_code": job_post.tenant_code or partner.partner_tenant_id,

            # ── Pipeline state at submission ──────────────────────────────────
            "pipeline_step": application.pipeline_step_name,
            "pipeline_step_order": application.pipeline_step_order,
            "pipeline_status": application.pipeline_status_name,
            "pipeline_status_order": application.pipeline_status_order,
        }

        # Enrich with profile details when available
        if profile:
            payload.update(
                {
                    "first_name": profile.first_name,
                    "last_name": profile.last_name,
                    "profile_id": str(application.profile_id),
                }
            )

        return payload
