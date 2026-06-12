import logging

from apps.integration.constants import DEFAULT_FIELD_MAPPINGS

logger = logging.getLogger(__name__)


def seed_default_field_mappings(partner) -> list:
    """
    Creates the pre-defined field mappings for a newly connected partner.

    Behaviour:
    - Skips any source_field already configured (preserves customisations).
    - Safe to call multiple times (idempotent per source_field).
    - Returns the list of newly created IntegrationFieldMapping objects.

    Called automatically in IntegrationExchangeView after the partner is saved,
    and exposed via POST /api/v1/integration/data-mapping/restore-defaults so
    admins can re-apply missing defaults without losing existing ones.
    """
    from apps.integration.models.job_platform import IntegrationFieldMapping

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

    if to_create:
        created = IntegrationFieldMapping.objects.bulk_create(to_create)
        logger.info(
            "seed_default_field_mappings: partner_id=%s seeded %d mappings",
            partner.id,
            len(created),
        )
        return created

    return []


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
            # Build ERP value → ConnectJob value lookup from nested value mappings
            value_lookup = {
                vm.target_value: vm.source_value
                for vm in mapping.value_mappings.all()
            }
            connectjob_value = value_lookup.get(str(erp_value))
            if connectjob_value is None:
                # No matching value mapping — fall back to raw ERP value
                logger.debug(
                    "transform_erp_payload: no value mapping for field '%s' value '%s'",
                    erp_key,
                    erp_value,
                )
                connectjob_value = erp_value
        else:
            connectjob_value = erp_value

        result[mapping.source_field] = connectjob_value

    # Fill in defaults for ConnectJob fields that the ERP payload omitted
    for mapping in mappings:
        if mapping.source_field not in result and mapping.default_value is not None:
            result[mapping.source_field] = mapping.default_value

    return result
