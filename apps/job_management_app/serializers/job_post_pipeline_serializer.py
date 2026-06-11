from apps.base.serializers.base_serializer import (
    BaseAndAuditSerializer,
    BaseReadOnlyFieldsSerializer,
)
from apps.job_management_app.models.job_post_pipeline_step_history_model import (
    JobPostPipelineStepHistoryModel,
)


class JobPostPipelineStepHistorySerializer(
    BaseAndAuditSerializer, BaseReadOnlyFieldsSerializer
):
    inject_company_id = False  # This serializer does not need company_id

    class Meta:
        model = JobPostPipelineStepHistoryModel
        fields = [
            "job_post",
            "step_name",
            "step_code",
        ]
