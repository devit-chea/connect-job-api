from django.utils import timezone as dtimezone

from rest_framework import serializers
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.auth_totp_mail.constants.invite_type_contants import (
    ALLOWED_MANUAL_STATUSES,
    InvitationStatus,
    InvitationType,
)
from apps.auth_totp_mail.models.invitation_models import Invitation
from apps.auth_totp_mail.models.mail_template_models import MailTemplate
from apps.auth_totp_mail.utils.invitation_utils import get_invitation_type_display
from apps.base.decorators.datetime_format_decorator import datetime_format_decorator
from apps.base.utils.file_management_util import FileURLService
from apps.job_management_app.models.job_application_model import JobApplicationModel
from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineConfigModel,
    JobPipelineConfigStepModel,
)


class SendInvitationSerializer(serializers.Serializer):
    job_application_id = serializers.IntegerField()
    mail_template_id = serializers.IntegerField()
    invitation_type = serializers.ChoiceField(
        choices=InvitationType.choices,
        error_messages={
            "invalid_choice": "Invalid invitation type.",
        },
    )
    additional_message = serializers.CharField(
        max_length=512, required=False, allow_blank=True
    )
    location = serializers.CharField(max_length=512, required=False, allow_blank=True)
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    metadata = serializers.JSONField(required=False, default=dict)
    invited_at = serializers.DateTimeField(
        required=True,
        allow_null=False,
        error_messages={
            "invalid": "Invalid datetime format. Expected format: YYYY-MM-DDTHH:MM:SS.",
            "null": "Invitation datetime is required.",
        },
    )
    pipeline_config_id = serializers.IntegerField()
    pipeline_step_id = serializers.IntegerField()

    def validate_invited_at(self, value):
        if value <= dtimezone.now():
            raise serializers.ValidationError(
                "Invitation datetime must be in the future."
            )
        return value

    def validate_job_application_id(self, value):
        try:
            job_app = JobApplicationModel.objects.get(
                id=value,
            )
        except JobApplicationModel.DoesNotExist:
            raise serializers.ValidationError("Job application not found.")
        self._job_application = job_app
        return value

    def validate_mail_template_id(self, value):
        try:
            template = MailTemplate.objects.get(
                id=value,
            )
        except MailTemplate.DoesNotExist:
            raise serializers.ValidationError("Mail template not found.")
        self._mail_template = template
        return value

    def validate_pipeline_config_id(self, value):
        try:
            pipeline_config = JobPipelineConfigModel.objects.get(
                id=value, is_active=True
            )
        except JobPipelineConfigModel.DoesNotExist:
            raise serializers.ValidationError("Pipeline config not found.")
        self._pipeline_config = pipeline_config
        return value

    def validate_pipeline_step_id(self, value):
        try:
            pipeline_step = JobPipelineConfigStepModel.objects.get(
                id=value, is_active=True
            )
        except JobPipelineConfigStepModel.DoesNotExist:
            raise serializers.ValidationError("Pipeline step not found.")
        self._pipeline_step = pipeline_step
        return value

    def validate(self, attrs):
        request = self.context["request"]

        # Inject audit fields from request
        attrs["create_ucp_id"] = request.user_company_profile_id
        attrs["create_uid"] = request.profile_id

        # Ensure pipeline_step belongs to pipeline_config
        pipeline_config = getattr(self, "_pipeline_config", None)
        pipeline_step = getattr(self, "_pipeline_step", None)
        if pipeline_config and pipeline_step:
            if pipeline_step.pipeline_config_id != pipeline_config.id:
                raise serializers.ValidationError(
                    "Pipeline step does not belong to the selected pipeline config."
                )
        return attrs


class InvitationResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = [
            "id",
            "job_application",
            "mail_template_id",
            "invitation_type",
            "subject_snapshot",
            "body_snapshot",
            "status",
            "invited_at",
            "additional_message",
            "location",
            "latitude",
            "longitude",
            "metadata",
            "create_date",
        ]
        read_only_fields = fields


class InvitationHistoryQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=InvitationStatus.choices, required=False)
    invitation_type = serializers.ChoiceField(
        choices=InvitationType.choices, required=False
    )


class InvitationHistoryResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = [
            "id",
            "job_application",
            "mail_template_id",
            "invitation_type",
            "subject_snapshot",
            "body_snapshot",
            "status",
            "invited_at",
            "additional_message",
            "location",
            "latitude",
            "longitude",
            "metadata",
            "create_date",
        ]
        read_only_fields = fields


class RescheduleInvitationSerializer(serializers.Serializer):
    mail_template_id = serializers.IntegerField(required=False)
    invitation_type = serializers.ChoiceField(
        choices=InvitationType.choices,
        error_messages={
            "invalid_choice": "Invalid invitation type.",
            "null": "Invitation type is required.",
        },
    )
    additional_message = serializers.CharField(
        max_length=512, required=False, allow_blank=True
    )
    location = serializers.CharField(max_length=512, required=False, allow_blank=True)
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    invited_at = serializers.DateTimeField(
        required=True,
        allow_null=False,
        error_messages={
            "invalid": "Invalid datetime format. Expected format: YYYY-MM-DDTHH:MM:SS.",
            "null": "Invitation datetime is required.",
        },
    )
    metadata = serializers.JSONField(required=False)

    def validate_invited_at(self, value):
        if value <= dtimezone.now():
            raise serializers.ValidationError(
                "Invitation datetime must be in the future."
            )
        return value

    def validate_mail_template_id(self, value):
        try:
            template = MailTemplate.objects.get(id=value)
        except MailTemplate.DoesNotExist:
            raise serializers.ValidationError("Mail template not found.")
        self._mail_template = template
        return value

    def validate(self, attrs):
        request = self.context["request"]
        attrs["write_ucp_id"] = request.user_company_profile_id
        attrs["write_uid"] = request.profile_id
        attrs["create_ucp_id"] = request.user_company_profile_id
        attrs["create_uid"] = request.profile_id

        return attrs


class UpdateInvitationStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ALLOWED_MANUAL_STATUSES)

    def validate(self, attrs):
        request = self.context["request"]
        attrs["write_ucp_id"] = request.user_company_profile_id
        attrs["write_uid"] = request.profile_id
        return attrs


@datetime_format_decorator(fields=["invited_at"], use_timezone=True)
class UpcomingEventSerializer(serializers.ModelSerializer):
    job_title = serializers.CharField(
        source="job_application.job_post.title", read_only=True
    )
    job_post_id = serializers.CharField(
        source="job_application.job_post.id", read_only=True
    )
    invitation_type_display = serializers.SerializerMethodField()
    display_rescheduled = serializers.SerializerMethodField()
    is_pipeline_visible = serializers.BooleanField(
        source="job_application.job_post.is_pipeline_visible", read_only=True
    )

    class Meta:
        model = Invitation
        fields = [
            "id",
            "mail_template_id",
            "invitation_type",
            "status",
            "invited_at",
            "additional_message",
            "location",
            "latitude",
            "longitude",
            "metadata",
            "job_title",
            "job_application",
            "company_id",
            "job_post_id",
            "is_rescheduled",
            "invitation_type_display",
            "display_rescheduled",
            "is_pipeline_visible",
        ]
        read_only_fields = fields

    def get_invitation_type_display(self, obj):
        return get_invitation_type_display(obj.invitation_type)

    def get_display_rescheduled(self, obj):
        return "Reschedule" if obj.is_rescheduled else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance.company)

        # Company Info
        data["company"] = {
            "id": instance.company.id,
            "name": instance.company.name,
            "email": instance.company.email,
            "profile_image_url": (presentation.get("profile_image") or {}).get(
                "file_path"
            ),
        }

        # Recruiter info
        recruiter = None
        create_ucp_id = getattr(
            instance.job_application.job_post,
            "create_ucp_id",
            None,
        )
        if create_ucp_id:
            user_company_profile = (
                UserCompanyProfile.objects.filter(id=create_ucp_id)
                .select_related("profile")
                .first()
            )

            if user_company_profile and user_company_profile.profile:
                profile = user_company_profile.profile

                recruiter_presentation = FileURLService.present_profile_images(profile)
                recruiter = {
                    "id": profile.id,
                    "first_name": profile.first_name,
                    "last_name": profile.last_name,
                    "full_name": f"{profile.first_name} {profile.last_name}".strip(),
                    "phone_number": profile.phone_number,
                    "profile_image_url": (
                        recruiter_presentation.get("profile_image") or {}
                    ).get("file_path"),
                }

        data["recruiter"] = recruiter

        return data


class UpcomingEventQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[InvitationStatus.PENDING, InvitationStatus.SENT],
        required=False,
    )
    invited_at_from = serializers.DateTimeField(required=False)
    invited_at_to = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        invited_at_from = attrs.get("invited_at_from")
        invited_at_to = attrs.get("invited_at_to")
        if invited_at_from and invited_at_to and invited_at_from > invited_at_to:
            raise serializers.ValidationError(
                {"invited_at_to": "End date must be after start date."}
            )
        return attrs
