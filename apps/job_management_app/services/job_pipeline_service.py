from rest_framework import serializers

from apps.base.models.company_model import Company
from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineConfigModel,
)
from apps.job_management_app.models.job_post_model import JobPostModel
from apps.job_management_app.serializers.job_post_pipeline_serializer import (
    JobPostPipelineStepHistorySerializer,
)


class JobPipelineService:

    @staticmethod
    def get_default_pipeline():
        """
        Prefer an operator-managed default;
        """
        company = Company.objects.filter(code="DEFAULT").first()
        qs = JobPipelineConfigModel.objects.filter(
            company=company, is_deleted=False, is_active=True, is_public=True
        )
        return qs.filter(is_default=True).first()

    @staticmethod
    def get_default_step(pipeline_config):
        if pipeline_config:
            return (
                pipeline_config.steps.filter(is_active=True, is_deleted=False)
                .order_by("order")
                .first()
            )
        return None

    @staticmethod
    def set_pipeline_step(validated_data):
        pipeline_config = validated_data.get("job_pipeline_config")
        if pipeline_config is None:
            pipeline_config = JobPipelineService.get_default_pipeline()
        if pipeline_config:
            default_step = JobPipelineService.get_default_step(pipeline_config)
            if not default_step:
                raise serializers.ValidationError(
                    {
                        "job_pipeline_config_id": "No default step found for this pipeline config."
                    }
                )
            validated_data["job_pipeline_step"] = default_step.name
            validated_data["job_pipeline_config"] = pipeline_config

    @staticmethod
    def save_step_history(job_post, step_name, step_code=None, context=None):
        data = {
            "job_post": job_post.id,
            "step_name": step_name,
            "step_code": step_code,
        }
        serializer = JobPostPipelineStepHistorySerializer(data=data, context=context)
        serializer.is_valid(raise_exception=True)
        serializer.save()

    @staticmethod
    def check_pipeline_usage(instance: JobPipelineConfigModel):
        """
        Block update/delete if this pipeline is used by any job post.
        """
        if JobPostModel.objects.filter(job_pipeline_config_id=instance).exists():
            raise serializers.ValidationError({
                "detail": "This pipeline is already used by one or more job posts."
            })
