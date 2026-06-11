import json
import logging
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import serializers

from apps.activity_tracking_app.serializers.activity_count_serializer import (
    JobPostUserActivityCountSerializer,
)
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.auth_oauth.serializers.profile_serializer import (
    ApplicantProfileRetrieveSerializer,
)
from apps.auth_oauth.services.user_profile_service import UserProfileService
from apps.auth_totp_mail.constants.invite_type_contants import InvitationStatus
from apps.auth_totp_mail.models.invitation_models import Invitation
from apps.auth_totp_mail.utils.invitation_utils import RESCHEDULE, get_invitation_type_display
from apps.base.decorators.datetime_format_decorator import (
    datetime_format_decorator,
    DateTimeFormat,
)
from apps.base.serializers.base_serializer import (
    BaseCompanySerializer,
    BaseReadOnlyFieldsSerializer,
    BaseDecimalRangeSerializerField,
)
from apps.base.utils.file_management_util import (
    FileURLService,
    ApplicationProfileImageListSerializer,
    resolve_profile_images,
)
from apps.elasticsearch_app.services.candidate_profile_services import (
    CandidateProfileService,
)
from apps.job_management_app.constants.job_application_types import JobApplicationStatus
from apps.job_management_app.constants.job_post_types import JobPostStatusTypes
from apps.job_management_app.models.job_application_model import (
    JobApplicationModel,
    JobApplicationQuestionAnswerModel,
)
from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineConfigStepModel,
    JobPipelineStatusConfigModel,
)
from apps.job_management_app.models.job_post_model import JobPostModel
from apps.job_management_app.models.job_question_model import JobPostQuestionModel
from apps.job_management_app.utils.job_post_utils import get_is_reapplicable
from apps.job_management_app.validators import ensure_status_allowed_for_step
from django.db.models.query import QuerySet

from apps.recruiter_management.serializers.recruiter_schedule_serializer import (
    InvitationScheduleByApplicationSerializer,
)

logger = logging.getLogger(__name__)


class JobPostForApplicationSerializer(serializers.ModelSerializer):

    class Meta:
        model = JobPostModel
        fields = [
            "id",
            "title",
            "location",
            "job_location",
            "post_date",
            "year_of_experience",
        ]

class JobApplicationQuestionAnswerSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    answer = serializers.CharField(allow_blank=True, required=False)


class JobApplicationRequestSerializer(serializers.Serializer):
    apply_message = serializers.CharField(required=True, allow_blank=True)
    meta_data = serializers.JSONField(required=False)
    cv_file_id = serializers.CharField(required=True)
    cover_letter_file_id = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    additional_file_ids = serializers.ListField(child=serializers.CharField(), required=False, allow_null=True)
    phone_number = serializers.CharField(required=False)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    answers = JobApplicationQuestionAnswerSerializer(many=True, required=False)
    applicant_name = serializers.CharField(read_only=True)
    current_position = serializers.CharField(read_only=True, allow_null=True)
    expected_salary = serializers.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        allow_null=True,
    )

    class Meta:
        fields = [
            "apply_message",
            "meta_data",
            "cv_file_id",
            "cover_letter_file_id",
            "additional_file_ids",
            "phone_number",
            "email",
            "answers",
            "current_position",
            "applicant_name",
            "expected_salary",
        ]

    def _inject_applicant_fields(self, data, request):
        ucp_id = getattr(request, "user_company_profile_id", None)
        applicant_name = None
        current_position = None

        if ucp_id:
            ucp = (
                UserCompanyProfile.objects.select_related("profile")
                .filter(id=ucp_id)
                .first()
            )
            if ucp and ucp.profile:
                p = ucp.profile
                applicant_name = getattr(p, "full_name", None)
                current_position = getattr(p, "current_position", None)
        data["applicant_name"] = applicant_name
        data["current_position"] = current_position
        return data

    
    def validate(self, data):
        # job_post_id passed in context from view
        request = self.context.get("request")
        user = request.user
        user_company_profile_id = request.user_company_profile_id
        profile_id = request.profile_id
        job_post_id = self.context.get("job_post_id")

        if not job_post_id:
            raise serializers.ValidationError("Job post ID is required in context.")

        # Validate job post exists
        job_post = JobPostModel.objects.filter(id=job_post_id).first()
        if not job_post:
            raise serializers.ValidationError("Invalid job post ID.")

        now = timezone.localdate()
        expire_date = getattr(job_post, "expire_date", None)
        if expire_date is not None and expire_date < now:
            raise serializers.ValidationError(
                {
                    "job_post": "This job posting has expired and is no longer accepting applications."
                }
            )

        status = getattr(job_post, "status", None)
        if status is not None and status in [
            JobPostStatusTypes.CLOSED,
            JobPostStatusTypes.INACTIVE,
            JobPostStatusTypes.SCHEDULED,
        ]:
            raise serializers.ValidationError(
                {
                    "job_post": "This job posting has closed and is no longer accepting applications."
                }
            )

        application_status = "new-applied"

        existing_app = JobApplicationModel.objects.filter(
            create_uid=user.id,
            create_ucp_id=user_company_profile_id,
            job_post_id=job_post_id,
        ).first()

        if existing_app:
            if existing_app.status == JobApplicationStatus.ACTIVE:
                logger.warning(
                    f"Duplicate application attempt: User {user.id} (UCP: {user_company_profile_id}) "
                    f"already has an ACTIVE application for Job {job_post_id}."
                )
                application_status = "re-applied"
            elif not get_is_reapplicable(job_post, request):
                raise serializers.ValidationError(
                    {
                        "job_post": "This job does not allow re-applications."
                    }
                )
            else:
                raise serializers.ValidationError(
                    {
                        "job_post": "You have already applied for this job and are not eligible to re-apply."
                    }
                )

        meta_data = data.get("meta_data") or {}
        if isinstance(meta_data, str):
            try:
                meta_data = json.loads(meta_data)
            except (json.JSONDecodeError, ValueError):
                meta_data = {}
        meta_data["application_status"] = application_status
        data["meta_data"] = meta_data

        answers = data.get("answers", [])

        # Validate question IDs belong to the job post
        valid_question_ids = set(
            JobPostQuestionModel.objects.filter(job_post_id=job_post_id).values_list(
                "id", flat=True
            )
        )
        errors = []
        for ans in answers:
            qid = ans.get("question_id")
            if qid not in valid_question_ids:
                errors.append(
                    f"Question ID {qid} is invalid or not related to this job post."
                )

        if errors:
            raise serializers.ValidationError({"answers": errors})
        data = self._inject_applicant_fields(data, request)
        return data


class JobApplicationAnswerResponseSerializer(serializers.ModelSerializer):
    question_title = serializers.CharField(source="question.question_title")
    is_required = serializers.BooleanField(source="question.is_required")

    class Meta:
        model = JobApplicationQuestionAnswerModel
        fields = ["question_id", "question_title", "is_required", "answer"]


class JobPostSummarySerializer(serializers.ModelSerializer):
    company = BaseCompanySerializer(read_only=True)
    is_reapplicable = serializers.SerializerMethodField(read_only=True)
    activity_count = serializers.SerializerMethodField()
    salary_range = BaseDecimalRangeSerializerField(read_only=True)
    
    class Meta:
        model = JobPostModel
        fields = [
            "id",
            "title",
            "location",
            "remote_type",
            "time_type",
            "priority",
            "company",
            "is_pipeline_visible",
            "is_reapplicable",
            "activity_count",
            "salary_type",
            "salary_range",
            "salary_currency",
        ]  # or whatever fields are useful

    def get_is_reapplicable(self, obj) -> bool:
        return get_is_reapplicable(obj, self.context.get("request"))
    
    @staticmethod
    def get_activity_count(obj):
        if (
            hasattr(obj, "user_activity_count")
            and obj.user_activity_count
        ):
            return JobPostUserActivityCountSerializer(obj.user_activity_count).data
        return {"view_count": 0, "save_count": 0, "apply_count": 0}

@datetime_format_decorator(
    fields=["create_date", "write_date", "post_date"],
)
class ApplicantJobPostSummarySerializer(BaseReadOnlyFieldsSerializer):
    company = BaseCompanySerializer(read_only=True)
    activity_count = serializers.SerializerMethodField()
    salary_range = BaseDecimalRangeSerializerField(read_only=True)
    is_applied = serializers.SerializerMethodField(read_only=True)
    is_saved = serializers.SerializerMethodField(read_only=True)
    is_reapplicable = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = JobPostModel
        fields = [
            "id",
            "title",
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
            "is_active",
            "status",
            "category",
            "priority",
            "salary_type",
            "salary_range",
            "salary_currency",
            "company",
            "job_level",
            "hire_no",
            "activity_count",
            "is_applied",
            "is_saved",
            "is_pipeline_visible",
            "year_of_experience",
            "is_reapplicable",
        ]

    @staticmethod
    def get_activity_count(obj):
        if hasattr(obj, "user_activity_count") and obj.user_activity_count:
            return JobPostUserActivityCountSerializer(obj.user_activity_count).data
        return {"view_count": 0, "save_count": 0, "apply_count": 0}

    def get_is_applied(self, obj):
        user = self.context["request"].user
        if not user or user.is_anonymous:
            return False

        return obj.user_states.filter(
            user_company_profile__user=user, status="applied"
        ).exists()
    
    def get_is_saved(self, obj):
        user = self.context["request"].user
        if not user or user.is_anonymous:
            return False

        return obj.user_states.filter(
            user_company_profile__user=user,
            is_saved=True
        ).exists()
    
    def get_is_reapplicable(self, obj) -> bool:
        return get_is_reapplicable(obj, self.context.get("request"))

class PipelineStepBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPipelineConfigStepModel
        fields = ("id", "name", "order", "is_default", "is_offer", "color")


class PipelineStatusBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPipelineStatusConfigModel
        fields = ("id", "name", "color")


class RecruiterUpdateStatusPipelineSerializer(serializers.Serializer):
    pipeline_step = PipelineStepBriefSerializer(read_only=True)
    pipeline_status = PipelineStatusBriefSerializer(read_only=True)


@datetime_format_decorator(
    fields=["apply_date", "create_date", "write_date"],
    field_formats={"apply_date": DateTimeFormat.DEFAULT},
    use_timezone=True,
)
class JobApplicationListResponseSerializer(serializers.ModelSerializer):
    job_post = JobPostSummarySerializer(read_only=True)
    pipeline_step = PipelineStepBriefSerializer(read_only=True)
    pipeline_status = PipelineStatusBriefSerializer(read_only=True)

    class Meta:
        model = JobApplicationModel
        list_serializer_class = ApplicationProfileImageListSerializer
        fields = [
            "id",
            "job_post",
            "apply_date",
            "pipeline_status",
            "applicant_current_position",
            "apply_message",
            "create_date",
            "write_date",
            "pipeline_step",
            "phone_number",
            "email",
            "employment_status",
            "applicant_name",
            "profile_id",
            "code",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        profile = getattr(instance, "profile", None)
        if not profile:
            data["applicant_name"] = data.get("applicant_name")
            data["profile_image_url"] = None
            return data

        urls = resolve_profile_images(profile, self.context, include_cover=False)
        data["applicant_name"] = profile.full_name or data.get("applicant_name")
        data["profile_image_url"] = urls["profile_image_url"]
        return data

class JobPostDetailSerializer(serializers.ModelSerializer):
    company = BaseCompanySerializer(read_only=True)

    class Meta:
        model = JobPostModel
        fields = "__all__"


class JobApplicationFileMapper:
    @classmethod
    def map(cls, instances):
        if instances is None:
            return []

        is_single = not isinstance(instances, (list, tuple, QuerySet))
        items = [instances] if is_single else instances
        
        all_file_ids = set()
        instance_files_meta = []
        
        for instance in items:
            f_map = cls._collect_file_ids(instance)
            instance_files_meta.append(f_map)
            for ids in f_map.values():
                all_file_ids.update(ids)

        if not all_file_ids:
            return [] if is_single else [[] for _ in items]

        uuid_map = cls._get_bulk_uuid_map(list(all_file_ids))

        try:
            presentation = FileURLService.map_by_file_ids(
                list(uuid_map.values())
            )
        except Exception:
            logger.exception(
                "Storage lookup failed",
                extra={"instances_count": len(items)},
            )
            return [] if is_single else [[] for _ in items]

        results = []
        for f_map in instance_files_meta:
            instance_result = {
                key: [presentation.get(uuid_map.get(fid)) for fid in ids]
                for key, ids in f_map.items()
            }
            results.append(instance_result)

        return results[0] if is_single else results

    @staticmethod
    def _collect_file_ids(instance):
        data = {}
        cv = getattr(instance, "cv_file_id", None)
        cl = getattr(instance, "cover_letter_file_id", None)
        additional = getattr(instance, "additional_file_ids", []) or []

        if cv: data["cv"] = [cv]
        if cl: data["cover_letter"] = [cl]
        if additional: data["additional"] = [f for f in additional if f]
        return data

    @staticmethod
    def _get_bulk_uuid_map(ids):
        service = UserProfileService()
        return {fid: service.to_uuid(fid) for fid in ids}


@datetime_format_decorator(
    fields=["apply_date", "create_date", "write_date"],
    field_formats={"apply_date": DateTimeFormat.ABBR_DATE},
    use_timezone=True,
)
class RecruiterJobApplicationDetailResponseSerializer(serializers.ModelSerializer):
    job_post = JobPostSummarySerializer(read_only=True)
    answers = JobApplicationAnswerResponseSerializer(many=True, read_only=True)
    pipeline_step = PipelineStepBriefSerializer(read_only=True)
    pipeline_status = PipelineStatusBriefSerializer(read_only=True)
    applicant_profile = serializers.SerializerMethodField()
    applicant_docs = serializers.SerializerMethodField()
    match_rate = serializers.SerializerMethodField(read_only=True)
    invitations = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = JobApplicationModel
        fields = [
            "id",
            "job_post",
            "profile_id",
            "job_post_id",
            "match_rate",
            "apply_date",
            "apply_message",
            "phone_number",
            "email",
            "meta_data",
            "answers",
            "create_date",
            "write_date",
            "pipeline_step",
            "pipeline_status",
            "applicant_profile",
            "employment_status",
            "applicant_docs",
            "invitations",
        ]

    def get_match_rate(self, obj):
        return CandidateProfileService.get_candidate_job_similarity_score(
            ucp_id=getattr(obj, "create_ucp_id", None),
            job_post_id=getattr(obj, "job_post_id", None),
        )

    def get_applicant_profile(self, obj):
        ucp_id = getattr(obj, "create_ucp_id", None)
        if not ucp_id:
            return None
        ucp = (
            UserCompanyProfile.objects.select_related("profile")
            .filter(pk=ucp_id)
            .first()
        )
        if not (ucp and ucp.profile):
            return None
        return ApplicantProfileRetrieveSerializer(
            ucp.profile, context=self.context
        ).data

    def get_applicant_docs(self, instance):
        return JobApplicationFileMapper.map(instance)

    def get_invitations(self, obj):
        if not obj.pipeline_config_id or not obj.pipeline_step_id:
            return None

        all_invitations = list(
            Invitation.objects.filter(
                job_application=obj,
                pipeline_config_id=obj.pipeline_config_id,
                pipeline_step_id=obj.pipeline_step_id,
                status__in=[
                    InvitationStatus.SENT,
                    InvitationStatus.PENDING,
                    InvitationStatus.CANCELLED,
                ],
            )
            .select_related("mail_template")
            .order_by("-create_date")
        )

        if not all_invitations:
            return None

        def collect_subs(root_id, invs):
            subs = []
            children = sorted(
                [inv for inv in invs if inv.rescheduled_from_id == root_id],
                key=lambda x: x.create_date,
                reverse=False,  # oldest first
            )
            for child in children:
                subs.append(child)
                subs.extend(collect_subs(child.id, invs))
            return subs

        referenced_ids = {
            inv.rescheduled_from_id
            for inv in all_invitations
            if inv.rescheduled_from_id is not None
        }

        entries = []
        visited_ids = set()

        # Originals = rescheduled_from_id is None AND referenced by others
        originals = [
            inv for inv in all_invitations
            if inv.rescheduled_from_id is None and inv.id in referenced_ids
        ]

        # Standalones = rescheduled_from_id is None AND not referenced by anyone
        standalones = [
            inv for inv in all_invitations
            if inv.rescheduled_from_id is None and inv.id not in referenced_ids
        ]

        for original in originals:
            if original.id in visited_ids:
                continue
            subs = collect_subs(original.id, all_invitations)
            entries.append({"main": original, "subs": subs})
            visited_ids.add(original.id)
            for sub in subs:
                visited_ids.add(sub.id)

        for standalone in standalones:
            if standalone.id in visited_ids:
                continue
            entries.append({"main": standalone, "subs": []})
            visited_ids.add(standalone.id)

         # Sort by main.id ASC  max unlimited.
        entries = sorted(entries, key=lambda x: x["main"].id)

        # Latest entry is last (ASC sort)
        latest_entry = entries[-1] if entries else None
        latest_invitation_id = latest_entry["main"].id if latest_entry else None
        latest_sub_id = (
            latest_entry["subs"][-1].id  # last = newest (oldest first order)
            if latest_entry and latest_entry["subs"]
            else None
        )

        result = []
        for entry in entries:
            main = entry["main"]
            subs = entry["subs"]

            serialized = InvitationSummarySerializer(
                main,
                context={
                    "latest_invitation_id": latest_invitation_id,
                    "latest_sub_id": latest_sub_id,
                    "subs": subs,
                },
            ).data
            result.append(serialized)

        return result

@datetime_format_decorator(
    fields=["invited_at"],
    field_formats={"invited_at": DateTimeFormat.DEFAULT},
    use_timezone=True,
)
class InvitationRescheduledChildSerializer(serializers.ModelSerializer):
    invitation_type_display = serializers.SerializerMethodField()
    is_latest = serializers.SerializerMethodField()
    transaction_title = serializers.SerializerMethodField()
    
    class Meta:
        model = Invitation
        fields = [
            "id",
            "invitation_type",
            "invited_at",
            "status",
            "location",
            "additional_message",
            "pipeline_config_id",
            "pipeline_step_id",
            "is_rescheduled",
            "rescheduled_from_id",
            "invitation_type_display",
            "longitude",
            "latitude",
            "is_latest",
            "transaction_title",
        ]

    def get_invitation_type_display(self, obj):
        return get_invitation_type_display(obj.invitation_type)

    def get_is_latest(self, obj) -> bool:
        latest_id = self.context.get("latest_id")
        return obj.id == latest_id

    def get_transaction_title(self, obj):
        latest_id = self.context.get("latest_id")
        if obj.id == latest_id:
            return RESCHEDULE
        return get_invitation_type_display(obj.invitation_type)
    
@datetime_format_decorator(
    fields=["invited_at"],
    field_formats={"invited_at": DateTimeFormat.DEFAULT},
    use_timezone=True,
)
class InvitationSummarySerializer(serializers.ModelSerializer):
    invitation_type_display = serializers.SerializerMethodField()
    is_latest = serializers.SerializerMethodField()
    transactions = serializers.SerializerMethodField()
    transaction_title = serializers.SerializerMethodField()
    
    class Meta:
        model = Invitation
        fields = [
            "id",
            "invitation_type",
            "invited_at",
            "status",
            "location",
            "additional_message",
            "pipeline_config_id",
            "pipeline_step_id",
            "is_rescheduled",
            "rescheduled_from_id",
            "invitation_type_display",
            "longitude",
            "latitude",
            "is_latest",
            "transactions",
            "transaction_title",
        ]

    def get_invitation_type_display(self, obj):
        return get_invitation_type_display(obj.invitation_type)

    def get_is_latest(self, obj) -> bool:
        latest_sub_id = self.context.get("latest_sub_id")
        latest_invitation_id = self.context.get("latest_invitation_id")
        if latest_sub_id is not None:
            return False
        return obj.id == latest_invitation_id

    def get_transactions(self, obj) -> list | None:
        subs = self.context.get("subs", [])

        if not subs:
            return None

        # subs already oldest first
        all_transactions = [obj] + subs
        latest_id = all_transactions[-1].id  # last = newest

        if len(all_transactions) > 2:
            display_transactions = [all_transactions[-2], all_transactions[-1]]
        else:
            display_transactions = all_transactions

        return InvitationRescheduledChildSerializer(
            display_transactions,
            many=True,
            context={"latest_id": latest_id},
        ).data
    
    def get_transaction_title(self, obj):
        latest_id = self.context.get("latest_invitation_id")
        if obj.id == latest_id:
            return RESCHEDULE
        return get_invitation_type_display(obj.invitation_type)
    
@datetime_format_decorator(
    fields=["apply_date", "create_date", "write_date"],
    field_formats={"apply_date": DateTimeFormat.DEFAULT},
    use_timezone=True,
)
class ApplicantJobApplicationDetailResponseSerializer(serializers.ModelSerializer):
    job_post = ApplicantJobPostSummarySerializer(read_only=True)
    is_saved = serializers.SerializerMethodField(read_only=True)
    invitations = serializers.SerializerMethodField(read_only=True)
    recruiter = serializers.SerializerMethodField()
    
    class Meta:
        model = JobApplicationModel
        fields = [
            "id",
            "job_post",
            "apply_date",
            "apply_message",
            "phone_number",
            "email",
            "meta_data",
            "create_date",
            "write_date",
            "pipeline_step",
            "pipeline_status",
            "employment_status",
            "is_saved",
            "invitations",
            "recruiter",   
            "pipeline_config_id",
            "pipeline_step_id",
        ]
        
    def get_is_saved(self, obj):
        user = self.context["request"].user
        if not user or user.is_anonymous:
            return False

        return obj.job_post.user_states.filter(
            user_company_profile__user=user,
            is_saved=True
        ).exists()

    def get_recruiter(self, obj):
        if not obj.job_post.create_ucp_id:
            return None
        ucp = (
            UserCompanyProfile.objects
            .select_related("profile")
            .filter(pk=obj.job_post.create_ucp_id)
            .first()
        )
        if not ucp or not ucp.profile:
            return None
        
        presentation = FileURLService.present_profile_images(ucp.profile)
        profile_image = (presentation.get("profile_image") or {}).get("file_path")

        return {"full_name": ucp.profile.full_name, "profile_image_url": profile_image}


    def get_invitations(self, obj):
        if not obj.pipeline_config_id or not obj.pipeline_step_id:
            return None

        all_invitations = list(
            Invitation.objects.filter(
                job_application=obj,
                pipeline_config_id=obj.pipeline_config_id,
                pipeline_step_id=obj.pipeline_step_id,
                status__in=[
                    InvitationStatus.SENT,
                    InvitationStatus.PENDING,
                    InvitationStatus.CANCELLED,
                ],
            )
            .select_related("mail_template")
            .order_by("-create_date")
        )

        if not all_invitations:
            return None

        def collect_subs(root_id, invs):
            subs = []
            children = sorted(
                [inv for inv in invs if inv.rescheduled_from_id == root_id],
                key=lambda x: x.create_date,
                reverse=False,  # oldest first
            )
            for child in children:
                subs.append(child)
                subs.extend(collect_subs(child.id, invs))
            return subs

        referenced_ids = {
            inv.rescheduled_from_id
            for inv in all_invitations
            if inv.rescheduled_from_id is not None
        }

        entries = []
        visited_ids = set()

        # Originals = rescheduled_from_id is None AND referenced by others
        originals = [
            inv for inv in all_invitations
            if inv.rescheduled_from_id is None and inv.id in referenced_ids
        ]

        # Standalones = rescheduled_from_id is None AND not referenced by anyone
        standalones = [
            inv for inv in all_invitations
            if inv.rescheduled_from_id is None and inv.id not in referenced_ids
        ]

        for original in originals:
            if original.id in visited_ids:
                continue
            subs = collect_subs(original.id, all_invitations)
            entries.append({"main": original, "subs": subs})
            visited_ids.add(original.id)
            for sub in subs:
                visited_ids.add(sub.id)

        for standalone in standalones:
            if standalone.id in visited_ids:
                continue
            entries.append({"main": standalone, "subs": []})
            visited_ids.add(standalone.id)

        # Sort by main.id DESC
        entries = sorted(entries, key=lambda x: x["main"].id, reverse=True)
        entries = entries[:2]  # max 2

        # Latest entry is last (ASC sort)
        latest_entry = entries[-1] if entries else None
        latest_invitation_id = latest_entry["main"].id if latest_entry else None
        latest_sub_id = (
            latest_entry["subs"][-1].id  # last = newest (oldest first order)
            if latest_entry and latest_entry["subs"]
            else None
        )

        result = []
        for entry in entries:
            main = entry["main"]
            subs = entry["subs"]

            serialized = InvitationSummarySerializer(
                main,
                context={
                    "latest_invitation_id": latest_invitation_id,
                    "latest_sub_id": latest_sub_id,
                    "subs": subs,
                },
            ).data
            result.append(serialized)

        return result

class RecruiterPipelineUpdateSerializer(serializers.Serializer):
    status_id = serializers.IntegerField(
        required=True,
        allow_null=False,
    )

    def validate(self, attrs):
        app = self.context.get("application")
        if not app:
            raise serializers.ValidationError("Missing application in context.")
        step = app.pipeline_step
        status = get_object_or_404(
            JobPipelineStatusConfigModel, pk=attrs["status_id"], is_active=True
        )
        ensure_status_allowed_for_step(step, status)
        attrs["status"] = status
        return attrs


@datetime_format_decorator(
    fields=["apply_date", "create_date", "write_date"],
    field_formats={"apply_date": DateTimeFormat.DEFAULT},
    use_timezone=True,
)
class RecruiterJobApplicationListResponseSerializer(serializers.ModelSerializer):
    job_post = JobPostForApplicationSerializer(read_only=True)
    pipeline_config = serializers.StringRelatedField()
    pipeline_step = PipelineStepBriefSerializer(read_only=True)
    match_rate = serializers.SerializerMethodField(read_only=True)
    pipeline_status = PipelineStatusBriefSerializer(read_only=True)

    class Meta:
        model = JobApplicationModel
        list_serializer_class = ApplicationProfileImageListSerializer
        fields = [
            "id",
            "job_post",
            "apply_date",
            "pipeline_status",
            "applicant_current_position",
            "apply_message",
            "create_date",
            "write_date",
            "pipeline_config",
            "pipeline_step",
            "phone_number",
            "email",
            "match_rate",
            "employment_status",
            "code",
        ]

    def get_match_rate(self, obj):
        return CandidateProfileService.get_candidate_job_similarity_score(
            ucp_id=getattr(obj, "create_ucp_id", None),
            job_post_id=getattr(obj, "job_post_id", None),
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        profile = getattr(instance, "profile", None)
        if not profile:
            data["applicant_name"] = None
            data["profile_image_url"] = None
            return data
        urls = resolve_profile_images(profile, self.context, include_cover=False)
        data["applicant_name"] = profile.full_name
        data["profile_image_url"] = urls["profile_image_url"]
        return data

class JobApplicationEmploymentStatusSerializer(serializers.ModelSerializer):
    employment_status = serializers.CharField(required=True, allow_null=False, )

    class Meta:
        model = JobApplicationModel
        fields = ["employment_status"]
