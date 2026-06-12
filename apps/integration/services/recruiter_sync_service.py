import logging

import requests as http_client
from django.conf import settings

from apps.integration.constants import ConnectorStatus
from apps.integration.models.job_platform import IntegrationPartner, IntegrationUserMapping

logger = logging.getLogger(__name__)


class RecruiterSyncService:
    """
    Syncs a newly created recruiter/admin user to the connected ERP (Wing Digital)
    and stores the mapping in IntegrationUserMapping for cross-system reference.

    Called asynchronously via Celery after a UserCompanyProfile is created for
    a company that has an active IntegrationPartner.

    The mapping record is created immediately (partner_user_id=None) so the
    local reference exists even if the ERP call fails. The partner_user_id is
    filled in once ERP responds successfully.
    """

    @staticmethod
    def sync_to_erp(ucp) -> None:
        """
        ucp: UserCompanyProfile instance (pre-fetched with user, profile, company)
        """
        company_id = str(ucp.company_id)

        partner = IntegrationPartner.objects.filter(
            organization_id=company_id,
            status=ConnectorStatus.ACTIVE,
        ).first()

        if not partner:
            logger.debug(
                "RecruiterSync: no active integration for company_id=%s — skipped",
                company_id,
            )
            return

        local_user_id = str(ucp.profile_id) if ucp.profile_id else str(ucp.user_id)

        # Create the mapping immediately — partner_user_id filled in after ERP responds
        mapping, _ = IntegrationUserMapping.objects.get_or_create(
            connection=partner,
            local_user_id=local_user_id,
            defaults={"partner_user_id": None},
        )

        payload = RecruiterSyncService._build_payload(ucp, partner)

        try:
            response = http_client.post(
                f"{settings.CONNECTOR_INTEGRATION_URL}"
                f"/api/connector-integration/users",
                json=payload,
                headers={"X-CONNECTOR-KEY": partner.partner_inbound_key},
                timeout=15,
            )
        except Exception as exc:
            logger.warning(
                "RecruiterSync: HTTP error ucp_id=%s error=%s",
                ucp.id, exc,
            )
            raise  # re-raise so Celery retries

        if response.status_code not in (200, 201):
            logger.warning(
                "RecruiterSync: ERP rejected ucp_id=%s status=%s body=%s",
                ucp.id, response.status_code, response.text[:300],
            )
            response.raise_for_status()

        partner_user_id = (
            response.json().get("user_id")
            or response.json().get("partner_user_id")
        )

        if partner_user_id:
            mapping.partner_user_id = str(partner_user_id)
            mapping.save(update_fields=["partner_user_id"])

        logger.info(
            "RecruiterSync: synced ucp_id=%s local_user_id=%s → partner_user_id=%s",
            ucp.id, local_user_id, partner_user_id,
        )

    @staticmethod
    def _build_payload(ucp, partner) -> dict:
        user = ucp.user
        profile = ucp.profile

        payload = {
            "connectjob_user_id": str(user.id),
            "connectjob_ucp_id": str(ucp.id),
            "role": ucp.type,
            "tenant_code": partner.partner_tenant_id,
            # Identity
            "username": user.username,
            "email": user.username,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "is_active": user.is_active,
        }

        if profile:
            payload.update({
                "connectjob_profile_id": str(profile.id),
                "first_name": profile.first_name or user.first_name or "",
                "last_name": profile.last_name or user.last_name or "",
                "phone_number": getattr(profile, "phone_number", None),
            })

        return payload
