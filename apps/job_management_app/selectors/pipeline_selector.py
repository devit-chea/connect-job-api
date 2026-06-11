from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineConfigModel,
    JobPipelineConfigStepModel,
    Status,
)


def get_job_pipeline_config(company_id, specific_config_id=None):
    """
    Service function to retrieve the correct pipeline configuration
    based on company ID fallback logic, with an optional filter for a specific config ID.
    """
    base_queryset = JobPipelineConfigModel.objects.filter(
        is_active=True,
        status=Status.ACTIVE,
    )

    # --- Step 1: Find the company-specific default (is_public=False) ---
    company_specific_config = (
        base_queryset.filter(
            company_id=company_id,
            is_default=True,
            is_public=False,
        )
        .values_list("id", flat=True)
        .first()
    )

    if company_specific_config:
        # If we found a company-specific config, use this as our primary target.
        # Now, check if a specific_config_id was requested within this scope.
        if specific_config_id is not None:
            # We must confirm the specific ID matches the record we just found.
            if company_specific_config == int(specific_config_id):
                return company_specific_config
            else:
                # The specific ID provided doesn't match the company's designated config.
                return None

        # No specific ID filter applied, return the company default.
        return company_specific_config

    # --- Step 2: If Step 1 yielded no results, fall back to the global public default ---
    global_default_config = (
        base_queryset.filter(
            is_default=True,
            is_public=True,
        )
        .values_list("id", flat=True)
        .first()
    )

    if global_default_config:
        # Note: The prompt implies that specific_config_id *only* applies to is_public=False configs (Step 1).
        # So, if we reach Step 2, we just return the global default regardless of specific_config_id.
        return global_default_config

    # --- Step 3: No configuration found at all ---
    return None


def get_pipeline_steps(pipeline_config_id):
    """
    Retrieves all active steps for a given pipeline configuration ID, ordered by their sequence.
    """
    return (
        JobPipelineConfigStepModel.objects.filter(
            pipeline_config_id=pipeline_config_id,
            is_active=True,
            status=Status.ACTIVE,
        )
        .order_by("order")
        .values("id", "name", "order", "color")
    )
