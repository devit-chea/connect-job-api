import logging
from datetime import datetime, timezone, timedelta

from django.db import transaction
from django.utils import timezone as dtimezone
from drf_extra_fields.relations import PresentablePrimaryKeyRelatedField
from rest_framework import serializers

from apps.activity_tracking_app.serializers.activity_count_serializer import (
    JobPostUserActivityCountSerializer,
)
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.base.decorators.datetime_format_decorator import datetime_format_decorator
from apps.base.models.geo_area_model import GeoArea
from apps.base.serializers.base_serializer import (
    BaseReadOnlyFieldsSerializer,
    BaseAndAuditSerializer,
    BaseCompanySerializer,
    BaseDecimalRangeSerializerField,
    BaseValidationSerializer,
    CompanyDetailSerializer,
)
from apps.base.serializers.company_serializer import CompanyLookUpSerializer
from apps.base.serializers.geo_area_serializer import GeoAreaInfoSerializer
from apps.base.utils.file_management_util import FileURLService
from apps.elasticsearch_app.services.applicant_recommend_service import (
    get_matching_applicants_with_scores,
)
from apps.elasticsearch_app.services.candidate_profile_services import (
    CandidateProfileService,
)
from apps.elasticsearch_app.services.job_matching_service import (
    calculate_similarity_score,
)
from apps.elasticsearch_app.services.job_post_es_sync_services import (
    JobPostESSyncServices,
)
from apps.job_management_app.constants.job_post_types import (
    JobPostSalaryTypes,
    JobPostStatusTypes,
)
from apps.job_management_app.models.job_category_model import JobCategoryModel
from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineConfigModel,
)
from apps.job_management_app.models.job_post_additional_field_model import (
    JobPostAdditionalFieldModel,
)
from apps.job_management_app.models.job_post_assigned_recruiter_model import (
    JobPostAssignedRecruiterModel,
)
from apps.job_management_app.models.job_post_model import JobPostModel
from apps.job_management_app.models.job_question_model import (
    JobPostQuestionModel,
    QuestionTypes,
)
from apps.job_management_app.serializers.job_post_assign_serializer import (
    AssignedRecruiterInfoSerializer,
)
from apps.job_management_app.services.job_pipeline_service import JobPipelineService
from apps.job_management_app.services.job_post_assign_service import (
    JobPostAssignNotificationService,
)
from apps.job_management_app.services.job_post_schedule_service import (
    JobPostScheduleService,
)
from apps.job_management_app.utils.job_post_utils import get_is_reapplicable

logger = logging.getLogger(__name__)

class AdditionalFieldItemSerializer(serializers.Serializer):
    code = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=True)
    description = serializers.CharField(required=False, allow_blank=True)


class JobPostQuestionSerializer(BaseValidationSerializer):
    choices = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
        source="choices_list",
    )

    class Meta:
        model = JobPostQuestionModel
        fields = [
            "id",
            "question_title",
            "question_type",
            "is_required",
            "choices",
            "order",
        ]

    def validate(self, attrs):
        question_type = attrs.get("question_type")
        choices = attrs.get("choices_list", [])

        if question_type in [QuestionTypes.SINGLE_CHOICE, QuestionTypes.MULTIPLE_CHOICE]:
            if not choices:
                raise serializers.ValidationError(
                    {"choices": f"Choices cannot be empty."}
                )

            if len(choices) < 2:
                raise serializers.ValidationError(
                    {"choices": f"Choices must contain at least 2 items."}
                )

        elif question_type == QuestionTypes.TEXT and choices:
            raise serializers.ValidationError(
                {"choices": f"Choices are not allowed for this question type."}
            )
        return attrs

class JobPipelineConfigReadSerializer(BaseReadOnlyFieldsSerializer):
    class Meta:
        model = JobPipelineConfigModel
        fields = ["id", "name", "description", "is_active", "is_deleted"]

class JobPostStatusUpdateSerializer(BaseAndAuditSerializer, BaseValidationSerializer):
    class Meta:
        model = JobPostModel
        fields = ["status"]

    def validate_status(self, value):
        allowed = {
            JobPostStatusTypes.ACTIVE.value,
            JobPostStatusTypes.INACTIVE.value,
        }
        if value not in allowed:
            raise serializers.ValidationError("Invalid job status.")
        return value

    def validate(self, attrs):
        instance = self.instance
        new_status = attrs.get("status")
        today = dtimezone.localdate()
        if instance.status == new_status:
            raise serializers.ValidationError(
                {"detail": f"Nothing change."}
            )
        if new_status == JobPostStatusTypes.ACTIVE.value:
            if instance.expire_date and instance.expire_date < today:
                raise serializers.ValidationError(
                    {
                        "detail": "Cannot publish an expired job. Please update expire date first."
                    }
                )
        return attrs

    def update(self, instance, validated_data):
        previous_status = instance.status
        new_status = validated_data.get("status")

        if new_status == JobPostStatusTypes.ACTIVE.value:
            instance.post_date = dtimezone.now()

        instance = super().update(instance, validated_data)

        if previous_status == JobPostStatusTypes.SCHEDULED:
            transaction.on_commit(
                lambda: JobPostScheduleService.cancel_publish(instance.id)
            )

        return instance


class JobPostSerializer(BaseAndAuditSerializer, BaseValidationSerializer):
    title = serializers.CharField(max_length=100, required=True, allow_blank=False)
    category = serializers.CharField(required=True, allow_blank=False)
    contract_type = serializers.CharField(required=True)
    time_type = serializers.CharField(required=True)
    remote_type = serializers.CharField(required=True)
    location = serializers.CharField(required=True)
    status = serializers.ChoiceField(
        choices=[
            JobPostStatusTypes.ACTIVE,
            JobPostStatusTypes.INACTIVE,
            JobPostStatusTypes.DRAFT,
            JobPostStatusTypes.SCHEDULED,
        ],
        required=True,
    )
    priority = serializers.CharField(required=True, allow_blank=False)
    salary_type = serializers.CharField(required=True, allow_blank=False)
    salary_range = BaseDecimalRangeSerializerField(required=False, allow_null=True)
    salary_currency = serializers.CharField(required=True, allow_blank=True)
    job_description = serializers.CharField(required=False, allow_blank=True)
    job_requirement = serializers.CharField(required=True, allow_blank=False)
    job_level = serializers.CharField(required=True, allow_blank=False)
    hire_no = serializers.IntegerField(
        required=True, error_messages={"required": "This field may not be null."}
    )
    questions = JobPostQuestionSerializer(many=True, required=False)
    natures = AdditionalFieldItemSerializer(many=True, required=False)
    job_pipeline_config = JobPipelineConfigReadSerializer(read_only=True)
    job_pipeline_config_id = serializers.PrimaryKeyRelatedField(
        source="job_pipeline_config",
        queryset=JobPipelineConfigModel.objects.all(),
        required=True,
        allow_null=True,
        write_only=True,
    )
    company = BaseCompanySerializer(read_only=True)
    post_date = serializers.DateTimeField(
        required=False,
        allow_null=True,
        input_formats=["%Y-%m-%d %H:%M:%S"],
        format="%Y-%m-%d %H:%M:%S",
    )
    job_location = PresentablePrimaryKeyRelatedField(
        queryset=GeoArea.objects.all(),
        presentation_serializer=GeoAreaInfoSerializer,
        required=True,
        allow_null=False,
    )
    year_of_experience = serializers.CharField(required=False, allow_blank=True)
    is_pipeline_visible = serializers.BooleanField(default=False, required=False)
    job_responsibility = serializers.CharField(required=True, allow_blank=False)
    assigned_ucp_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        write_only=True,
        help_text="UCP IDs of recruiters to assign to this job post.",
    )

    class Meta:
        model = JobPostModel
        fields = [
            "id",
            "title",
            "tenant_code",
            "job_code",
            "location",
            "job_location",
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
            "questions",
            "is_active",
            "status",
            "category",
            "natures",
            "priority",
            "salary_type",
            "salary_range",
            "salary_currency",
            "company_id",
            "company",
            "job_level",
            "hire_no",
            "job_pipeline_config",
            "job_pipeline_config_id",
            "job_pipeline_step",
            "job_location",
            "year_of_experience",
            "assigned_ucp_ids",
            "is_pipeline_visible",
        ]

    default_values = {
        "salary_currency": "USD",
        "hire_no": 0,
    }

    def get_job_pipeline_config(self, obj):
        config = obj.job_pipeline_config
        if not config:
            return None
        return {
            "id": config.id,
            "name": config.name,  # Replace with any fields you want exposed
        }

    def cross_field_validation(self, attrs):
        status = attrs.get("status")
        post_date = attrs.get("post_date")
        publishing = status in (JobPostStatusTypes.ACTIVE, JobPostStatusTypes.SCHEDULED)

        if publishing and not post_date:
            raise serializers.ValidationError(
                {"post_date": "This field is required."}
            )

        if not publishing and post_date:
            raise serializers.ValidationError(
                {"detail": "A posting date has already been selected. Drafts cannot include a posting date."}
            )
        # expire_date must be after post_date
        expire_date = attrs.get("expire_date")

        now = dtimezone.now().date()
        if expire_date and expire_date <= now:
            raise serializers.ValidationError(
                {"expire_date": "Expire date must be after post date."}
            )

        # Salary rules
        salary_type = attrs.get("salary_type")
        salary_range = attrs.get("salary_range")
        errors = {}
        # Step 1: Check salary_range presence for each salary type
        if salary_type == JobPostSalaryTypes.NEGOTIABLE.name:
            if salary_range not in (None, [], [None], [None, None]):
                errors["salary_range"] = "Salary must be null for negotiable."
        elif salary_type in (
            JobPostSalaryTypes.FIXED.name,
            JobPostSalaryTypes.RANGE.name,
        ):
            if salary_range.lower is None:
                errors["salary_min"] = "This field is required."
            if salary_range.upper is None:
                errors["salary_max"] = "This field is required."
        # Step 2: Check salary_range values is valid
        if "salary_min" not in errors and "salary_max" not in errors:
            if salary_type == JobPostSalaryTypes.FIXED.name:
                if salary_range.lower != salary_range.upper:
                    errors["detail"] = (
                        "Minimum salary and maximum salary must be the same."
                    )

            elif salary_type == JobPostSalaryTypes.RANGE.name:
                if salary_range.lower >= salary_range.upper:
                    errors["detail"] = (
                        "Minimum salary must be less than maximum salary."
                    )
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # Group and serialize additional fields by field_name
        grouped_fields = JobPostAdditionalFieldModel.objects.filter(
            job_post=instance, is_deleted=False
        ).values("code", "name", "description", "field_name")

        mapping = {
            "job_levels": [],
            "natures": [],
        }

        for item in grouped_fields:
            field_name = item["field_name"]
            if field_name in mapping:
                mapping[field_name].append(
                    {
                        "code": item["code"],
                        "name": item["name"],
                        "description": item["description"],
                    }
                )

        data.update(mapping)
        assignments = (
            instance.job_post_assigned_recruiters
            .filter(is_deleted=False)
            .select_related("assigned_ucp__profile")
        )
        data["assigned_recruiters"] = AssignedRecruiterInfoSerializer(
            assignments, many=True, context=self.context
        ).data
        return data

    def _sync_assigned_recruiters(self, job_post, ucp_ids: list):
        """
        Compute the diff between the current assignment list and the requested one,
        add/remove records accordingly.
        """
        from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
        from apps.auth_oauth.models.profile_model import Profile

        request = self.context.get("request")
        assigner_ucp_id = str(getattr(request, "user_company_profile_id", None))
        assigner_user_id = getattr(request, "user_id", None)

        assigner_profile = (
            Profile.objects.filter(usercompanyprofile__id=assigner_ucp_id).first()
        )

        desired_ids = set(ucp_ids)
        current_ids = set(
            job_post.job_post_assigned_recruiters.filter(is_deleted=False).values_list("assigned_ucp_id", flat=True)
        )

        to_remove = current_ids - desired_ids
        if to_remove:
            for assignment in job_post.job_post_assigned_recruiters.filter(
                assigned_ucp_id__in=to_remove
            ):
                assignment.write_uid = assigner_user_id
                assignment.write_ucp_id = assigner_ucp_id
                assignment.delete()

        # Add newly assigned recruiters
        to_add = desired_ids - current_ids
        if not to_add:
            return

        new_ucps = UserCompanyProfile.objects.filter(
            id__in=to_add,
            company_id=getattr(request, "company_id", None),
        ).select_related("profile")
        if new_ucps.count() != len(to_add):
            raise serializers.ValidationError({
                "detail": "Recruiters are invalid or do not belong to this company."
            })
        for ucp in new_ucps:
            obj = JobPostAssignedRecruiterModel.objects.create(
                job_post=job_post,
                assigned_ucp=ucp,
                create_ucp_id=assigner_ucp_id,
                create_uid=assigner_user_id,
            )
            obj.assigned_ucp = ucp  # already fetched with profile
            JobPostAssignNotificationService.notify_assigned(obj, job_post, assigner_profile)

    @transaction.atomic
    def create(self, validated_data):
        assigned_ucp_ids = validated_data.pop("assigned_ucp_ids", [])
        question_data = validated_data.pop("questions", [])
        natures = validated_data.pop("natures", [])
        post_date = validated_data.pop("post_date", None)

        # If publish or active
        if validated_data.get("status") in (JobPostStatusTypes.ACTIVE, JobPostStatusTypes.SCHEDULED):
            validated_data["post_date"], validated_data["status"] = JobPostScheduleService.resolve(
                post_date=post_date,
            )


        # Auto-set job_pipeline_step based on config
        JobPipelineService.set_pipeline_step(validated_data)

        job_post = super().create(validated_data)

        # Save initial pipeline step history
        request = self.context.get("request")
        JobPipelineService.save_step_history(
            job_post=job_post,
            step_name=job_post.job_pipeline_step,
            context={"request": request},
        )

        for q in question_data:
            JobPostQuestionModel.objects.create(job_post=job_post, **q)
        self._create_additional_fields(job_post, natures, "natures")

        if assigned_ucp_ids:
            self._sync_assigned_recruiters(job_post, assigned_ucp_ids)

        if job_post.status == JobPostStatusTypes.SCHEDULED:
            transaction.on_commit(
                lambda: JobPostScheduleService.schedule_publish(job_post.id, job_post.post_date)
            )
        return job_post

    @transaction.atomic
    def update(self, instance, validated_data):
        today = dtimezone.localdate()
        if (
            instance.expire_date
            and instance.expire_date < today
            and instance.status != JobPostStatusTypes.DRAFT
        ):
            raise serializers.ValidationError(
                {"detail": "Cannot update an expired job."}
            )
        previous_status = instance.status
        assigned_ucp_ids = validated_data.pop("assigned_ucp_ids", None)
        question_data = validated_data.pop("questions", [])
        natures = validated_data.pop("natures", [])
        post_date = validated_data.pop("post_date", None)

        requested_status = validated_data.get("status")
        publishing = requested_status in (JobPostStatusTypes.ACTIVE, JobPostStatusTypes.SCHEDULED)
        if publishing:
            validated_data["post_date"], validated_data["status"] = JobPostScheduleService.resolve(
                post_date=post_date,
                current_post_date=instance.post_date,
            )
        elif post_date:
            validated_data["post_date"] = post_date

        old_step = instance.job_pipeline_step
        new_step = validated_data.get("job_pipeline_step", old_step)

        # Save step history only if pipeline step changed
        if new_step != old_step:
            request = self.context.get("request")
            JobPipelineService.save_step_history(
                job_post=instance, step_name=new_step, context={"request": request}
            )

        # Clear old related data and create new
        JobPostQuestionModel.objects.filter(job_post=instance).delete()
        JobPostAdditionalFieldModel.objects.filter(job_post=instance).delete()

        # Call base update() to inject audit and company_id and update instance fields
        instance = super().update(instance, validated_data)

        for q in question_data:
            JobPostQuestionModel.objects.create(job_post=instance, **q)
        self._create_additional_fields(instance, natures, "natures")
        # Only sync if the field was explicitly sent (None means omitted)
        if assigned_ucp_ids is not None:
            self._sync_assigned_recruiters(instance, assigned_ucp_ids)

        if instance.status == JobPostStatusTypes.SCHEDULED:
            # Newly scheduled or post_date changed → register/update crontab
            transaction.on_commit(
                lambda: JobPostScheduleService.schedule_publish(instance.id, instance.post_date)
            )
        elif previous_status == JobPostStatusTypes.SCHEDULED:
            # Was SCHEDULED but changed to ACTIVE/DRAFT/INACTIVE → cancel crontab
            transaction.on_commit(
                lambda: JobPostScheduleService.cancel_publish(instance.id)
            )

        return instance

    def _create_additional_fields(self, job_post, items, field_name):
        for item in items:
            JobPostAdditionalFieldModel.objects.create(
                job_post=job_post, field_name=field_name, **item
            )


@datetime_format_decorator(
    fields=["write_date", "create_date", "post_date"],
)
class JobPostListSerializer(BaseReadOnlyFieldsSerializer):
    activity_count = serializers.SerializerMethodField()
    recommended_count = serializers.SerializerMethodField()
    company = CompanyLookUpSerializer(read_only=True)
    status_name = serializers.SerializerMethodField()
    is_reapplicable = serializers.SerializerMethodField(read_only=True)
    assigned_recruiters = serializers.SerializerMethodField()

    class Meta:
        model = JobPostModel
        fields = [
            "id",
            "company",
            "title",
            "remote_type",
            "time_type",
            "post_date",
            "expire_date",
            "priority",
            "status",
            "job_pipeline_step",
            "job_description",
            "hire_no",
            "activity_count",
            "category",
            "recommended_count",
            "status_name",
            "is_reapplicable",
            "assigned_recruiters",
        ]
        read_only_fields = fields

    def get_assigned_recruiters(self, obj):
        assignments = obj.job_post_assigned_recruiters.filter(
            is_deleted=False
        ).select_related("assigned_ucp__profile")
        return AssignedRecruiterInfoSerializer(assignments, many=True, context=self.context).data


    @staticmethod
    def get_activity_count(obj):
        if hasattr(obj, "user_activity_count") and obj.user_activity_count:
            return JobPostUserActivityCountSerializer(obj.user_activity_count).data
        return {"view_count": 0, "save_count": 0, "apply_count": 0}

    # Recommended Count
    def get_recommended_count(self, obj):
        try:
            # We call the service but discard the detailed list, we only need the count.
            _, count = get_matching_applicants_with_scores(
                job_post=obj, min_score_threshold=1
            )
            return count
        except Exception as e:
            print(f"Error calculating match count for Job {obj.id}: {e}")
            return 0  # Default to 0 on failure
    def get_status_name(self, obj):
        today = dtimezone.localdate()
        mapping = {
            JobPostStatusTypes.ACTIVE.value: "Publish",
            JobPostStatusTypes.INACTIVE.value: "Unpublished",
            JobPostStatusTypes.DRAFT.value: "Draft",
            JobPostStatusTypes.SCHEDULED.value: "Scheduled",
        }
        if (
            obj.status == JobPostStatusTypes.ACTIVE.value
            and obj.expire_date
            and obj.expire_date < today
        ):
            return "Close"
        return mapping.get(obj.status, obj.status)

    def get_is_reapplicable(self, obj) -> bool:
        return get_is_reapplicable(obj, self.context.get("request"))

@datetime_format_decorator(
    fields=["create_date", "write_date", "post_date", "applied_at"],
    use_timezone=True,
)
class JobPostDetailSerializer(BaseReadOnlyFieldsSerializer):
    questions = JobPostQuestionSerializer(many=True, read_only=True)
    natures = AdditionalFieldItemSerializer(many=True, read_only=True)
    job_pipeline_config = JobPipelineConfigReadSerializer(read_only=True)
    company = BaseCompanySerializer(read_only=True)
    activity_count = serializers.SerializerMethodField()
    salary_range = BaseDecimalRangeSerializerField(read_only=True)
    is_saved = serializers.SerializerMethodField(read_only=True)
    is_applied = serializers.SerializerMethodField(read_only=True)
    match_rate = serializers.SerializerMethodField()
    status_name = serializers.SerializerMethodField()
    applied_at = serializers.SerializerMethodField(read_only=True)
    is_reapplicable = serializers.SerializerMethodField(read_only=True)
    posted_by = serializers.SerializerMethodField()
    assigned_recruiters = serializers.SerializerMethodField()

    class Meta:
        model = JobPostModel
        fields = [
            "id",
            "title",
            "tenant_code",
            "job_code",
            "location",
            "job_location",
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
            "questions",
            "is_active",
            "status",
            "category",
            "natures",
            "priority",
            "salary_type",
            "salary_range",
            "salary_currency",
            "company",
            "job_level",
            "hire_no",
            "job_pipeline_config",
            "job_pipeline_step",
            "activity_count",
            "is_saved",
            "is_applied",
            "year_of_experience",
            "match_rate",
            "is_pipeline_visible",
            "status_name",
            "applied_at",
            "is_reapplicable",
            "posted_by",
            "assigned_recruiters",
        ]

    def get_assigned_recruiters(self, obj):
        assignments = obj.job_post_assigned_recruiters.filter(
            is_deleted=False
        ).select_related("assigned_ucp__profile")
        return AssignedRecruiterInfoSerializer(
            assignments, many=True, context=self.context
        ).data

    @staticmethod
    def get_activity_count(obj):
        if hasattr(obj, "user_activity_count") and obj.user_activity_count:
            return JobPostUserActivityCountSerializer(obj.user_activity_count).data
        return {"view_count": 0, "save_count": 0, "apply_count": 0}

    def get_is_saved(self, obj):
        user = self.context["request"].user
        if not user or user.is_anonymous:
            return False

        return obj.user_states.filter(
            user_company_profile__user=user, is_saved=True
        ).exists()

    def get_posted_by(self, obj):
        if not obj.create_ucp_id:
            return None
        ucp = (
            UserCompanyProfile.objects
            .select_related("profile")
            .filter(pk=obj.create_ucp_id)
            .first()
        )
        if not ucp or not ucp.profile:
            return None

        presentation = FileURLService.present_profile_images(ucp.profile)
        profile_image = (presentation.get("profile_image") or {}).get("file_path")

        return {"full_name": ucp.profile.full_name, "profile_image_url": profile_image}

    def get_is_applied(self, obj):
        user = self.context["request"].user
        if not user or user.is_anonymous:
            return False

        return obj.user_states.filter(
            user_company_profile__user=user, status="applied"
        ).exists()

    def get_match_rate(self, obj):
        score = 0
        request = self.context.get("request", None)
        try:
            job = JobPostESSyncServices.get_job_post(obj.id)
            if request.user.is_authenticated:
                candidate = CandidateProfileService.get_candidate_profile(
                    request.user_company_profile_id
                )
                if candidate:
                    score = calculate_similarity_score(candidate[0], job)
            return score
        except Exception as e:
            logger.error(f"Fail: {e}")
            return score

    def get_status_name(self, obj):
        today = dtimezone.localdate()
        mapping = {
            JobPostStatusTypes.ACTIVE.value: "Publish",
            JobPostStatusTypes.INACTIVE.value: "Unpublished",
            JobPostStatusTypes.DRAFT.value: "Draft",
            JobPostStatusTypes.SCHEDULED.value: "Scheduled",
        }
        if (
            obj.status == JobPostStatusTypes.ACTIVE.value
            and obj.expire_date
            and obj.expire_date < today
        ):
            return "Close"
        return mapping.get(obj.status, obj.status)

    def get_applied_at(self, obj):
        user = self.context["request"].user
        if not user or user.is_anonymous:
            return None

        state = (
            obj.user_states
            .filter(
                user_company_profile__user=user,
                status="applied"
            )
            .order_by("-applied_at")  # latest application
            .first()
        )

        return state.applied_at if state else None


    def get_is_reapplicable(self, obj) -> bool:
        return get_is_reapplicable(obj, self.context.get("request"))

    def _get_category_icon(self, category_name: str) -> str | None:
        if not category_name:
            return None

        # Hit cache if list serializer already pre-warmed it
        cached_map = self.context.get("category_icon_map")
        if cached_map is not None:
            return cached_map.get(category_name)

        # Detail path: single DB query, no map construction
        cat = JobCategoryModel.objects.filter(name=category_name).only(
            "id", "name", "profile_picture_id"
        ).first()

        if not cat or not cat.profile_picture_id:
            return None

        presentation = FileURLService.present_profile_images(cat)
        return (presentation.get("profile_image") or {}).get("file_path")


    def _get_category_icon_map(self, category_names: list[str]) -> dict[str, str | None]:
        if "category_icon_map" in self.context:
            return self.context["category_icon_map"]

        unique_names = {name for name in category_names if name}

        categories = JobCategoryModel.objects.filter(
            name__in=unique_names
        ).only("id", "name", "profile_picture_id")

        icon_map: dict[str, str | None] = {}
        for cat in categories:
            if not cat.profile_picture_id:
                icon_map[cat.name] = None
                continue
            presentation = FileURLService.present_profile_images(cat)
            icon_map[cat.name] = (
                presentation.get("profile_image") or {}
            ).get("file_path")

        self.context["category_icon_map"] = icon_map
        return icon_map


    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data is None:
            return None

        category_name = data.get("category") or None
        data["category_icon"] = self._get_category_icon(category_name)

        return data


class JobCountSerializer(serializers.Serializer):
    profile_image_url = serializers.CharField(allow_null=True)
    name = serializers.CharField(allow_null=True)
    count = serializers.IntegerField()
    id = serializers.IntegerField(allow_null=True)


class CountsQuerySerializer(serializers.Serializer):
    exclude_null = serializers.BooleanField(default=True, required=False)
    page = serializers.IntegerField(required=False)
    page_size = serializers.IntegerField(required=False)
    paging = serializers.BooleanField(required=False, default=True)


class CategorySerializer(serializers.Serializer):
    search = serializers.CharField(required=False)
    page = serializers.IntegerField(required=False)
    page_size = serializers.IntegerField(required=False)
    paging = serializers.BooleanField(required=False, default=True)


class SimilarJobPostListSerializer(BaseReadOnlyFieldsSerializer):
    activity_count = serializers.SerializerMethodField()
    company = CompanyDetailSerializer(read_only=True)

    class Meta:
        model = JobPostModel
        fields = [
            "id",
            "title",
            "remote_type",
            "time_type",
            "post_date",
            "expire_date",
            "priority",
            "status",
            "job_pipeline_step",
            "job_description",
            "hire_no",
            "activity_count",
            "category",
            "company",
        ]
        read_only_fields = fields

    @staticmethod
    def get_activity_count(obj):
        if hasattr(obj, "user_activity_count") and obj.user_activity_count:
            return JobPostUserActivityCountSerializer(obj.user_activity_count).data
        return {"view_count": 0, "save_count": 0, "apply_count": 0}
