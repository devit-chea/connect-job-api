import logging
from typing import Optional

from django.db import transaction

from apps.base.constants.base_constants import CompanyStatusChoices, EntryTypeChoices
from apps.base.models.company_model import AccessType, Company

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _es_sync_company(company: Company) -> None:
    """
    Push a single Company document to Elasticsearch.

    Adjust the import path and document class to match your project's
    django-elasticsearch-dsl setup (e.g. search.documents.CompanyDocument).
    """
    try:
        from apps.elasticsearch_app.search.global_search_document import (
            CompanyDocument,
        )

        CompanyDocument().update(company)
        logger.debug("ES sync OK  company_id=%s", company.pk)
    except Exception as exc:  # pragma: no cover
        # Log but don't blow up the HTTP response — ES is eventually consistent.
        logger.exception("ES sync FAILED company_id=%s error=%s", company.pk, exc)


def _build_company_fields(validated_data: dict) -> dict:
    """
    Map the inbound validated payload to Company model field names.
    Only keys that were actually supplied are included (safe for partial update).
    """
    field_map = {
        # direct 1-to-1 mappings
        "name": "name",
        "email": "email",
        "website": "website",
        "phone_number": "phone_number",
        "street": "street",
        "address": "address",
        "city_name": "city_name",
        "postal_code": "postal_code",
        "latitude": "latitude",
        "longitude": "longitude",
        "description": "description",
        "about_me": "about_me",
        "industry": "industry",
        "company_size": "company_size",
        "found_date": "found_date",
        "logo_description": "logo_description",
        "profile_picture_id": "profile_picture_id",
        "cover_picture_id": "cover_picture_id",
        "linkedin_email": "linkedin_email",
        "code": "code",
        "integrate_domain": "integrate_domain",
        # FK ids
        "city_id": "city_id",
        "country_id": "country_id",
    }

    return {
        model_field: validated_data[payload_key]
        for payload_key, model_field in field_map.items()
        if payload_key in validated_data
    }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class CompanyIntegrationService:
    """
    Encapsulates all business logic for the partner-integration lifecycle:

        register  – create a new integrated Company record
        sync      – update an existing integrated Company record
        deactivate – soft-disable without deleting
        get_by_domain – lookup helper used by views & other services
    """

    # ── Register ─────────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def register(validated_data: dict) -> Company:
        """
        Create a brand-new Company that originates from an external platform.

        Sets:
            is_integrate  = True
            access_type   = EXTERNAL
            entry_type    = INTEGRATION  (add this choice if not present)
            status        = ACTIVE
        """
        fields = _build_company_fields(validated_data)
        fields.update(
            {
                "is_integrate": True,
                "access_type": AccessType.EXTERNAL,
                # Use INTEGRATION entry type if it exists, else DEFAULT
                "entry_type": getattr(
                    EntryTypeChoices, "INTEGRATION", EntryTypeChoices.DEFAULT
                ).value,
                "status": CompanyStatusChoices.APPROVED.value,
                "is_active": True,
            }
        )

        company = Company.objects.create(**fields)
        logger.info(
            "Integration company CREATED id=%s domain=%s",
            company.pk,
            company.integrate_domain,
        )

        _es_sync_company(company)
        return company

    # ── Sync (partial update) ─────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def sync(company: Company, validated_data: dict) -> Company:
        """
        Merge the inbound payload into an existing integrated Company.
        Only supplied fields are written; others are left untouched.
        """
        fields = _build_company_fields(validated_data)

        for attr, value in fields.items():
            setattr(company, attr, value)

        # Always refresh the sync timestamp via updated_at (AbstractBaseModel)
        company.save()

        logger.info(
            "Integration company SYNCED id=%s domain=%s",
            company.pk,
            company.integrate_domain,
        )

        _es_sync_company(company)
        return company

    # ── Deactivate ────────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def deactivate(company: Company) -> Company:
        """Soft-disable an integrated company without removing the DB row."""
        company.is_active = False
        company.status = CompanyStatusChoices.REJECTED.value
        company.save(update_fields=["is_active", "status", "updated_at"])

        logger.info(
            "Integration company DEACTIVATED id=%s domain=%s",
            company.pk,
            company.integrate_domain,
        )

        _es_sync_company(company)
        return company

    # ── Reactivate ────────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def reactivate(company: Company) -> Company:
        company.is_active = True
        company.status = CompanyStatusChoices.APPROVED.value
        company.save(update_fields=["is_active", "status", "updated_at"])

        logger.info(
            "Integration company REACTIVATED id=%s domain=%s",
            company.pk,
            company.integrate_domain,
        )

        _es_sync_company(company)
        return company

    # ── Lookup helpers ────────────────────────────────────────────────────────

    @staticmethod
    def get_by_domain(domain: str) -> Optional[Company]:
        return Company.objects.filter(
            integrate_domain=domain.lower().rstrip("/"),
            is_integrate=True,
        ).first()

    @staticmethod
    def get_by_id(company_id: int) -> Optional[Company]:
        return Company.objects.filter(
            pk=company_id,
            is_integrate=True,
        ).first()

    @staticmethod
    def list_active() -> "QuerySet[Company]":
        return (
            Company.objects.filter(
                is_integrate=True,
                is_active=True,
            )
            .select_related("country", "city")
            .order_by("-created_at")
        )
