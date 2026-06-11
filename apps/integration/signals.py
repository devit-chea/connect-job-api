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

from apps.base.models.company_model import Company

logger = logging.getLogger(__name__)


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
