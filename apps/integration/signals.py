"""
signals.py  company_integration

Wires a post_save signal on Company so that any save (not just integration
API calls) keeps Elasticsearch up to date for integrated companies.

Register this in your AppConfig.ready():

    # company_integration/apps.py
    class CompanyIntegrationConfig(AppConfig):
        name = "company_integration"

        def ready(self):
            import company_integration.signals  # noqa: F401
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.base.models.company_model import Company
from apps.job_management_app.models.job_application_model import JobApplicationModel

logger = logging.getLogger(__name__)


@receiver(post_save, sender=UserCompanyProfile)
def on_recruiter_created(sender, instance: UserCompanyProfile, created: bool, **kwargs):
    """
    After a new UserCompanyProfile is saved for a company that has an active
    integration, dispatch an async Celery task to:
      1. Create an IntegrationUserMapping record locally (partner_user_id=None)
         so the cross-system reference exists immediately.
      2. Call WingDigital to register the user on the ERP side and fill in
         partner_user_id once ERP responds.

    Only fires on CREATE. Does not filter by type so all recruiter roles
    (admin_recruiter, recruiter, etc.) are synced for integrated companies.
    """
    if not created:
        return

    if not instance.company_id:
        return

    try:
        from apps.integration.tasks import sync_recruiter_to_erp
        sync_recruiter_to_erp.delay(instance.id)
        logger.debug(
            "Signal: queued ERP recruiter sync for ucp_id=%s company_id=%s",
            instance.id, instance.company_id,
        )
    except Exception as exc:
        logger.warning(
            "Signal: failed to queue ERP recruiter sync ucp_id=%s error=%s",
            instance.id, exc,
        )


@receiver(post_save, sender=JobApplicationModel)
def on_application_created(sender, instance: JobApplicationModel, created: bool, **kwargs):
    """
    After a new JobApplicationModel is saved, dispatch an async Celery task to
    push the applicant into the connected ERP (Wing Digital) pipeline.

    Only fires on CREATE (not updates). Skipped silently if:
    - the job post's company has no active IntegrationPartner
    - Celery is unavailable (import error caught gracefully)
    """
    if not created:
        return

    try:
        from apps.integration.tasks import sync_applicant_to_erp
        sync_applicant_to_erp.delay(instance.id)
        logger.debug(
            "Signal: queued ERP applicant sync for application_id=%s", instance.id
        )
    except Exception as exc:
        # Never let a signal failure affect the applicant's submit flow
        logger.warning(
            "Signal: failed to queue ERP sync for application_id=%s error=%s",
            instance.id,
            exc,
        )


@receiver(post_save, sender=Company)
def sync_integrated_company_to_es(sender, instance: Company, created: bool, **kwargs):
    """
    After any Company save, re-index to ES if it is an integrated company.

    We import CompanyDocument lazily to avoid circular imports and to
    gracefully degrade when ES is not configured (e.g. during tests).
    """
    if not instance.is_integrate:
        return

    try:
        from apps.elasticsearch_app.search.global_search_document import (
            CompanyDocument,
        )

        CompanyDocument().update(instance)
        logger.debug("Signal: ES synced company_id=%s created=%s", instance.pk, created)
    except ImportError:
        logger.warning(
            "Signal: CompanyDocument not found — ES sync skipped for company_id=%s",
            instance.pk,
        )
    except Exception as exc:
        logger.exception(
            "Signal: ES sync error company_id=%s error=%s", instance.pk, exc
        )
