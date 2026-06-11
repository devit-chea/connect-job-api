import json
import logging
from attrs import field
from django.db import models
from datetime import datetime, time, timezone
from django.utils import timezone as dtimezone
from rest_framework import serializers

from apps.base.models.geo_area_model import GeoArea
from apps.job_management_app.constants.job_post_types import (
    JobPostPriorityTypes,
    JobPostPrivacyTypes,
    JobPostSalaryCurrencyTypes,
    JobPostSalaryTypes,
    JobPostStatusTypes,
)
from apps.job_management_app.models.job_category_model import JobCategoryModel
from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineConfigModel,
)
from apps.job_management_app.models.job_post_model import JobPostModel
from apps.job_management_app.models.job_question_model import JobPostQuestionModel
from apps.job_management_app.serializers.job_post_serializer import (
    JobPostQuestionSerializer,
)
from apps.job_management_app.services.job_pipeline_service import JobPipelineService
from apps.job_management_app.tasks.job_repost_tasks import publish_scheduled_job_post


class JobPostRepostSerializer(serializers.Serializer):
    post_date = serializers.DateTimeField(required=False, allow_null=True, default=None)

    expire_date = serializers.DateField(required=True)

    # Optional overrides before repost
    job_pipeline_config_id = serializers.IntegerField(required=False, allow_null=True)
    job_pipeline_step = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    is_pipeline_visible = serializers.BooleanField(required=False)

    # Editable job details before repost
    title = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    location = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    time_type = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    remote_type = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    privacy_type = serializers.ChoiceField(
        choices=JobPostPrivacyTypes.choices, required=False, allow_null=True
    )
    contract_type = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    job_responsibility = serializers.CharField(
        required=True, allow_null=False, allow_blank=False
    )
    benefits = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    job_requirement = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    job_description = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    category = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    priority = serializers.ChoiceField(
        choices=JobPostPriorityTypes.choices, required=False, allow_null=True
    )
    salary_type = serializers.ChoiceField(
        choices=JobPostSalaryTypes.choices, required=False, allow_null=True
    )
    salary_range = serializers.ListField(
        child=serializers.DecimalField(max_digits=12, decimal_places=2),
        required=False,
        allow_null=True,
    )
    salary_currency = serializers.ChoiceField(
        choices=JobPostSalaryCurrencyTypes.choices, required=False, allow_null=True
    )
    job_level = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    hire_no = serializers.IntegerField(required=False, allow_null=True)
    job_location_id = serializers.IntegerField(required=False, allow_null=True)
    job_category_id = serializers.IntegerField(required=False, allow_null=True)
    year_of_experience = serializers.CharField(required=False, allow_blank=True)

    @staticmethod
    def _resolve_post_date_and_status(data):
        now = dtimezone.now()
        today = now.date()

        post_date = data.get("post_date")

        if post_date is None:
            # Not provided — publish immediately as today
            data["post_date"] = today
            data["post_date_aware"] = now  # already aware, no conversion needed
            data["resolved_status"] = JobPostStatusTypes.PUBLISHED
        else:
            if isinstance(post_date, datetime):
                post_date = post_date.date()
                data["post_date"] = post_date

            if post_date < today:
                raise serializers.ValidationError(
                    "Posting date cannot be in the past."
                )
            elif post_date == today:
                # Explicitly passed today — still publish immediately
                data["post_date_aware"] = now
                data["resolved_status"] = JobPostStatusTypes.PUBLISHED
            else:
                # Future date — schedule it
                data["post_date_aware"] = dtimezone.make_aware(
                    datetime.combine(post_date, time.min),
                    dtimezone.get_current_timezone()
                )
                data["resolved_status"] = JobPostStatusTypes.SCHEDULED

        return data

    def validate(self, data):
        original = self.context.get("original")

        if not original:
            raise serializers.ValidationError("Original job post not found.")

        now = dtimezone.now().date()
        original_expire_date = getattr(original, "expire_date", None)
        is_expired = original_expire_date is not None and original_expire_date < now
        is_closed = original.status == JobPostStatusTypes.CLOSED

        if not is_expired and not is_closed:
            raise serializers.ValidationError(
                "Only closed or expired job posts can be reposted."
            )

        # TODO: After got confirm or any update it will enable back.
        # Block repost if an active repost from this job already exists
        # active_repost = (
        #     JobPostModel.objects.filter(
        #         reposted_from=original,
        #     )
        #     .filter(models.Q(expire_date__isnull=True) | models.Q(expire_date__gte=now))
        #     .exclude(status=JobPostStatusTypes.CLOSED)
        #     .first()
        # )

        # if active_repost:
        #     raise serializers.ValidationError(
        #         f"Job post '{original.title}' has already been reposted and the reposted job "
        #         f"(ID: {active_repost.id}) is still active until {active_repost.expire_date}. "
        #         f"You cannot repost again until the reposted job has expired or been closed."
        #     )

        # Validate and resolve job_location_id if provided
        job_location_id = data.get("job_location_id")
        if job_location_id:
            job_location = GeoArea.objects.filter(id=job_location_id).first()
            if not job_location:
                raise serializers.ValidationError(
                    {"job_location_id": "Invalid job location ID."}
                )
            data["resolved_job_location"] = job_location
        else:
            data["resolved_job_location"] = original.job_location

        # Validate and resolve job_category_id if provided
        job_category_id = data.get("job_category_id")
        if job_category_id:
            job_category = JobCategoryModel.objects.filter(id=job_category_id).first()
            if not job_category:
                raise serializers.ValidationError(
                    {"job_category_id": "Invalid job category ID."}
                )
            data["resolved_job_category"] = job_category
        else:
            data["resolved_job_category"] = original.job_category

        # Validate job_pipeline_config_id if provided
        pipeline_config_id = data.get("job_pipeline_config_id")
        if pipeline_config_id:
            if pipeline_config_id is None:
                pipeline_config = JobPipelineService.get_default_pipeline()
        if pipeline_config_id:
            pipeline_config = JobPipelineConfigModel.objects.filter(
                id=pipeline_config_id
            ).first()
            if not pipeline_config:
                raise serializers.ValidationError(
                    {"job_pipeline_config_id": "Invalid pipeline config ID."}
                )
            default_step = JobPipelineService.get_default_step(pipeline_config)
            if not default_step:
                raise serializers.ValidationError(
                    {
                        "job_pipeline_config_id": "No default step found for this pipeline config."
                    }
                )
            data["job_pipeline_step"] = default_step.name
            data["resolved_pipeline_config"] = pipeline_config
        else:
            data["resolved_pipeline_config"] = original.job_pipeline_config

        # Validate salary_range list [lower, upper]
        salary_range = data.get("salary_range")
        if salary_range is not None:
            if len(salary_range) != 2:
                raise serializers.ValidationError(
                    {
                        "salary_range": "salary_range must contain exactly two values [lower, upper]."
                    }
                )
            if salary_range[0] > salary_range[1]:
                raise serializers.ValidationError(
                    {"salary_range": "Lower salary must not exceed upper salary."}
                )

        # Resolve post_date and status together
        data = self._resolve_post_date_and_status(data)
    
        # Default post_date to today if not provided
        post_date = data.get("post_date")
        if post_date is None:
            post_date = now
        elif isinstance(post_date, datetime):
            post_date = post_date.date()
        data["post_date"] = post_date

        # Backdate policy — disallow past posting dates
        if post_date < now:
            raise serializers.ValidationError("Posting date cannot be in the past.")

        # Expiry date must be in the future
        if data["expire_date"] <= now:
            raise serializers.ValidationError("Expiry date must be in the future.")

        # Ensure posting date is before expiry date
        if post_date >= data["expire_date"]:
            raise serializers.ValidationError(
                "Posting date must be before the expiry date."
            )

        # Resolve status based on post_date
        if post_date == now:
            data["resolved_status"] = JobPostStatusTypes.ACTIVE
        else:
            data["resolved_status"] = JobPostStatusTypes.SCHEDULED

        return data

    def save(self):
        original = self.context.get("original")
        request = self.context.get("request")
        resolved_status = self.validated_data["resolved_status"]
        post_date = self.validated_data["post_date"]
    
        def override(field):
            return self.validated_data.get(field, getattr(original, field))

        new_job_post = JobPostModel.objects.create(
            # Overridable job detail fields
            title=override("title"),
            location=override("location"),
            time_type=override("time_type"),
            remote_type=override("remote_type"),
            privacy_type=override("privacy_type"),
            contract_type=override("contract_type"),
            job_responsibility=override("job_responsibility"),
            benefits=override("benefits"),
            job_requirement=override("job_requirement"),
            job_description=override("job_description"),
            category=override("category"),
            priority=override("priority"),
            salary_type=override("salary_type"),
            salary_range=override("salary_range"),
            salary_currency=override("salary_currency"),
            job_level=override("job_level"),
            hire_no=override("hire_no"),
            year_of_experience=override("year_of_experience"),
            # Copied non-editable fields
            tenant_code=original.tenant_code,
            job_code=original.job_code,
            # Resolved FK fields
            job_pipeline_config=self.validated_data["resolved_pipeline_config"],
            job_pipeline_step=self.validated_data.get(
                "job_pipeline_step", original.job_pipeline_step
            ),
            is_pipeline_visible=self.validated_data.get(
                "is_pipeline_visible", original.is_pipeline_visible
            ),
            job_location=self.validated_data["resolved_job_location"],
            job_category=self.validated_data["resolved_job_category"],
            # Scheduling fields
            # post_date=post_date_aware,
            post_date=self.validated_data["post_date_aware"],
            expire_date=self.validated_data.get("expire_date"),
            status=resolved_status,
            is_active=True,
            # Lineage tracking
            reposted_from=original,
            reposted_at=dtimezone.now(),
            # Ownership
            create_uid=request.user_id,
            create_ucp_id=request.user_company_profile_id,
            company_id=request.company_id,
        )

        # Copy related questions
        questions = JobPostQuestionModel.objects.filter(job_post=original)
        if questions.exists():
            JobPostQuestionModel.objects.bulk_create(
                [
                    JobPostQuestionModel(
                        job_post=new_job_post,
                        question_title=q.question_title,
                        question_type=q.question_type,
                        is_required=q.is_required,
                        choices=q.choices,
                        order=q.order,
                    )
                    for q in questions
                ]
            )

        # Save initial pipeline step history
        JobPipelineService.save_step_history(
            job_post=new_job_post,
            step_name=new_job_post.job_pipeline_step,
            context={"request": request},
        )

        # Schedule celery task to auto-publish if future date
        if resolved_status == JobPostStatusTypes.SCHEDULED:
            publish_at = self.validated_data["post_date_aware"]
            publish_scheduled_job_post.apply_async(
                args=[str(new_job_post.id)],
                eta=publish_at,
            )

        return new_job_post


class JobRePostDetailSerializer(serializers.ModelSerializer):
    questions = JobPostQuestionSerializer(many=True, read_only=True)
    reposted_from = serializers.SerializerMethodField()
    salary_range = serializers.SerializerMethodField()

    class Meta:
        model = JobPostModel
        fields = [
            "id",
            "title",
            "tenant_code",
            "job_code",
            "location",
            "post_date",
            "expire_date",
            "time_type",
            "remote_type",
            "privacy_type",
            "contract_type",
            "job_responsibility",
            "benefits",
            "job_requirement",
            "job_description",
            "is_active",
            "status",
            "category",
            "priority",
            "salary_type",
            "salary_range",
            "salary_currency",
            "job_level",
            "hire_no",
            "job_pipeline_config",
            "job_pipeline_step",
            "job_location",
            "job_category",
            "year_of_experience",
            "is_pipeline_visible",
            "reposted_from",
            "reposted_at",
            "questions",
        ]

    def get_reposted_from(self, obj):
        if not obj.reposted_from:
            return None
        return {
            "id": obj.reposted_from.id,
            "title": obj.reposted_from.title,
            "status": obj.reposted_from.status,
            "post_date": obj.reposted_from.post_date,
            "expire_date": obj.reposted_from.expire_date,
        }

    def get_salary_range(self, obj):
        if not obj.salary_range:
            return None
        return {
            "lower": obj.salary_range.lower,
            "upper": obj.salary_range.upper,
        }
