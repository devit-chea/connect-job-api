import logging

from apps.integration.constants import DEFAULT_FIELD_MAPPINGS, DEFAULT_CATEGORY_VALUE_MAPPINGS

logger = logging.getLogger(__name__)


def seed_default_field_mappings(partner) -> list:
    """
    Creates the pre-defined field mappings for a newly connected partner and
    seeds value mappings for the 'category' field automatically.

    Behaviour:
    - Skips any source_field already configured (preserves customisations).
    - Safe to call multiple times (idempotent per source_field / target_value).
    - Returns the list of newly created IntegrationFieldMapping objects.
    """
    from apps.integration.models.job_platform import (
        IntegrationFieldMapping,
        IntegrationValueMapping,
    )

    existing_source_fields = set(
        IntegrationFieldMapping.objects.filter(partner=partner)
        .values_list("source_field", flat=True)
    )

    to_create = []
    for source_field, target_field, mapping_type, default_value in DEFAULT_FIELD_MAPPINGS:
        if source_field in existing_source_fields:
            continue
        to_create.append(
            IntegrationFieldMapping(
                partner=partner,
                source_field=source_field,
                target_field=target_field,
                mapping_type=mapping_type,
                default_value=default_value,
                is_active=True,
            )
        )

    created = []
    if to_create:
        created = IntegrationFieldMapping.objects.bulk_create(to_create)
        logger.info(
            "seed_default_field_mappings: partner_id=%s seeded %d field mappings",
            partner.id,
            len(created),
        )

    # Seed default job category value mappings for the 'category' field
    _seed_category_value_mappings(partner)

    return created


def _seed_category_value_mappings(partner) -> None:
    """
    Seeds the 9 standard job category value mappings under the 'category' field.
    Each entry in DEFAULT_CATEGORY_VALUE_MAPPINGS provides a list of ERP labels
    that all map to the same ConnectJob category; they are stored comma-joined.
    Idempotent — skips any source_value already present.
    """
    from apps.integration.models.job_platform import (
        IntegrationFieldMapping,
        IntegrationValueMapping,
    )

    category_mapping = IntegrationFieldMapping.objects.filter(
        partner=partner,
        source_field="category",
        is_active=True,
    ).first()

    if not category_mapping:
        return

    existing_sources = set(
        category_mapping.value_mappings.values_list("source_value", flat=True)
    )

    to_create = []
    for source_value, target_values in DEFAULT_CATEGORY_VALUE_MAPPINGS:
        if source_value in existing_sources:
            continue
        stored = ",".join(v.strip() for v in target_values if v.strip())
        to_create.append(
            IntegrationValueMapping(
                field_mapping=category_mapping,
                source_value=source_value,
                target_value=stored,
            )
        )

    if to_create:
        IntegrationValueMapping.objects.bulk_create(to_create)
        logger.info(
            "_seed_category_value_mappings: partner_id=%s seeded %d value mappings",
            partner.id,
            len(to_create),
        )


def transform_erp_payload(partner_id: str, erp_payload: dict) -> dict:
    """
    Transforms a raw ERP job post payload into ConnectJob field names and values.

    Steps:
      1. Load all active IntegrationFieldMappings for the partner (one DB query).
      2. Build a lookup keyed by ERP field name (target_field).
      3. For each key in the ERP payload, find the matching ConnectJob field name
         (source_field). If the field has value mappings, translate the value too.
      4. Apply default_value for any ConnectJob fields not present in the result.

    Returns a dict ready to pass into the job post creation serializer.
    """
    from apps.integration.models.job_platform import IntegrationFieldMapping

    mappings = list(
        IntegrationFieldMapping.objects
        .filter(partner_id=partner_id, is_active=True)
        .prefetch_related("value_mappings")
    )

    # ERP field name → mapping object
    erp_to_mapping = {m.target_field: m for m in mappings}

    result: dict = {}

    for erp_key, erp_value in erp_payload.items():
        mapping = erp_to_mapping.get(erp_key)
        if not mapping:
            logger.debug("transform_erp_payload: unmapped ERP field '%s' skipped", erp_key)
            continue

        if mapping.mapping_type == "mapped":
            # Build ERP label → ConnectJob value lookup.
            # target_value may be a comma-separated list (e.g. category field),
            # so each individual label is registered as a separate lookup key.
            value_lookup = {}
            for vm in mapping.value_mappings.all():
                for label in vm.target_value.split(","):
                    label = label.strip()
                    if label:
                        value_lookup[label] = vm.source_value
            connectjob_value = value_lookup.get(str(erp_value))
            if connectjob_value is None:
                # No value mapping matched — use default_value if configured
                # (e.g. "Other" for job category), otherwise keep the raw ERP value.
                if mapping.default_value is not None:
                    connectjob_value = mapping.default_value
                    logger.debug(
                        "transform_erp_payload: field '%s' value '%s' unmatched"
                        " → using default '%s'",
                        erp_key, erp_value, mapping.default_value,
                    )
                else:
                    connectjob_value = erp_value
                    logger.debug(
                        "transform_erp_payload: field '%s' value '%s' unmatched"
                        " → keeping raw ERP value",
                        erp_key, erp_value,
                    )
        else:
            connectjob_value = erp_value

        result[mapping.source_field] = connectjob_value

    # Fill in defaults for ConnectJob fields that the ERP payload omitted
    for mapping in mappings:
        if mapping.source_field not in result and mapping.default_value is not None:
            result[mapping.source_field] = mapping.default_value

    return result
