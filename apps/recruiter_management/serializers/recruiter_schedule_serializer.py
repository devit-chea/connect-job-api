from rest_framework import serializers
from apps.auth_totp_mail.constants.invite_type_contants import InvitationType
from apps.auth_totp_mail.models.invitation_models import Invitation
from apps.auth_totp_mail.utils.invitation_utils import get_invitation_type_display
from apps.base.decorators.datetime_format_decorator import (
    DateTimeFormat,
    datetime_format_decorator,
)
from apps.job_management_app.selectors.user_company_profile_selector import (
    get_ucp_by_id,
)
from apps.base.serializers.base_serializer import BaseAndAuditSerializer
from apps.job_management_app.models.job_application_model import JobApplicationModel
from apps.auth_oauth.serializers.profile_serializer import (
    ApplicantProfileRetrieveSerializer,
)


class RecruiterScheduleSerializer(BaseAndAuditSerializer):
    class Meta:
        model = Invitation
        fields = [
            "id",
        ]


@datetime_format_decorator(
    fields=["invited_at"],
    field_formats={"invited_at": DateTimeFormat.DEFAULT},
    use_timezone=True,
)
class InvitationScheduleListSerializer(BaseAndAuditSerializer):
    job_title = serializers.CharField(source="job_post.title", read_only=True)
    latest_invitation = serializers.SerializerMethodField()

    class Meta:
        model = JobApplicationModel
        fields = [
            "id",
            "applicant_name",
            "phone_number",
            "email",
            "job_title",
            "latest_invitation",
        ]

    def get_latest_invitation(self, obj):
        invitation = getattr(obj, "latest_invitation", None)
        if not invitation:
            return None
        return InvitationScheduleByApplicationSerializer(invitation).data


class InvitationScheduleByApplicationListSerializer(serializers.ModelSerializer):
    applicant_name = serializers.CharField(
        source="job_application.applicant_name", read_only=True
    )
    phone_number = serializers.CharField(
        source="job_application.phone_number", read_only=True
    )
    email = serializers.EmailField(source="job_application.email", read_only=True)
    job_title = serializers.CharField(
        source="job_application.job_post.title", read_only=True
    )
    invitation_type_display = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            "id",
            "applicant_name",
            "invitation_type",
            "invited_at",
            "phone_number",
            "email",
            "job_title",
            "status",
            "pipeline_config_id",
            "pipeline_step_id",
            "is_rescheduled",
            "rescheduled_from_id",
            "invitation_type_display",
        ]

    def get_invitation_type_display(self, obj):
        return get_invitation_type_display(obj.invitation_type)


@datetime_format_decorator(
    fields=["invited_at"],
    field_formats={"invited_at": DateTimeFormat.DEFAULT},
    use_timezone=True,
)
class InvitationScheduleByApplicationSerializer(serializers.ModelSerializer):
    invitation_type_display = serializers.SerializerMethodField()
    is_latest = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            "id",
            "invitation_type",
            "invited_at",
            "status",
            "location",
            "additional_message",
            "metadata",
            "pipeline_config_id",
            "pipeline_step_id",
            "is_rescheduled",
            "rescheduled_from_id",
            "invitation_type_display",
            "longitude",
            "latitude",
            "is_latest",
            "create_date",
        ]

    def get_invitation_type_display(self, obj):
        return get_invitation_type_display(obj.invitation_type)

    def get_is_latest(self, obj) -> bool:
        latest_invitation_id = self.context.get("latest_invitation_id")
        if latest_invitation_id is not None:
            return obj.id == latest_invitation_id
        return not obj.is_rescheduled


@datetime_format_decorator(
    fields=["invited_at"],
    field_formats={"invited_at": DateTimeFormat.DEFAULT},
    use_timezone=True,
)
class RecruiterInvitationScheduleListSerializer(serializers.ModelSerializer):
    applicant_name = serializers.CharField(
        source="job_application.applicant_name", read_only=True
    )
    phone_number = serializers.CharField(
        source="job_application.phone_number", read_only=True
    )
    email = serializers.EmailField(source="job_application.email", read_only=True)
    job_title = serializers.CharField(
        source="job_application.job_post.title", read_only=True
    )
    job_application_id = serializers.UUIDField(
        source="job_application.id", read_only=True
    )
    invitation_type_display = serializers.SerializerMethodField()
    applicant_profile = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            "id",
            "job_application_id",
            "applicant_name",
            "phone_number",
            "email",
            "job_title",
            "invitation_type",
            "invited_at",
            "status",
            "location",
            "additional_message",
            "metadata",
            "is_rescheduled",
            "pipeline_config_id",
            "pipeline_step_id",
            "invitation_type_display",
            "applicant_profile",
        ]

    def get_applicant_profile(self, obj):
        ucp_id = getattr(obj.job_application, "create_ucp_id", None)
        if not ucp_id:
            return None

        ucp = get_ucp_by_id(ucp_id)
        if not (ucp and ucp.profile):
            return None
        return ApplicantProfileRetrieveSerializer(
            ucp.profile, context=self.context
        ).data

    def get_invitation_type_display(self, obj):
        return get_invitation_type_display(obj.invitation_type)
