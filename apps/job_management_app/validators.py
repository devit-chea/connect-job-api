from django.core.exceptions import ValidationError

from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineConfigStepModel,
    JobPipelineStatusConfigModel,
    JobPipelineStepStatusConfigModel,
)


def allowed_status_ids_for_step(step: JobPipelineConfigStepModel) -> set[int]:
    """Allowed = {default, success, failed} from the step defaults row."""
    if not step:
        return set()
    step_id = getattr(step, "id", step)
    return set(
        JobPipelineStepStatusConfigModel.objects.filter(
            step_id=step_id, is_deleted=False, status__is_active=True
        ).values_list("status_id", flat=True)
    )


def ensure_step_in_pipeline(step: JobPipelineConfigStepModel, pipeline_config_id: int):
    """Raise if the step doesn't belong to the app's pipeline."""
    if step and step.pipeline_config_id != pipeline_config_id:
        raise ValidationError(
            {"pipeline_step": "Step does not belong to the application's pipeline."}
        )


def ensure_status_allowed_for_step(
    step: JobPipelineConfigStepModel, status: JobPipelineStatusConfigModel
):
    allowed = allowed_status_ids_for_step(step)
    if status.id not in allowed:
        raise ValidationError({"pipeline_status": "Status not allowed for step."})
