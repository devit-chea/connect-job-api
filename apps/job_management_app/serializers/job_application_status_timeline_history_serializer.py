from rest_framework import serializers

from apps.auth_totp_mail.models.invitation_models import Invitation
from apps.auth_totp_mail.utils.invitation_utils import get_invitation_type_display
from apps.base.decorators.datetime_format_decorator import (
    datetime_format_decorator,
    DateTimeFormat,
)
from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineStatusConfigModel,
)
from apps.job_management_app.serializers.job_application_serializer import (
    InvitationSummarySerializer,
)


class TimelineStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPipelineStatusConfigModel
        fields = ["id", "name", "color"]


@datetime_format_decorator(
    fields=["date"],
    field_formats={"date": DateTimeFormat.ABBR_DATE},
    use_timezone=True,
)
class ApplicationStatusItemSerializer(serializers.Serializer):
    step_id = serializers.IntegerField()
    step_name = serializers.CharField()
    order = serializers.IntegerField()
    status = TimelineStatusSerializer(allow_null=True)
    date = serializers.DateTimeField(allow_null=True)
    is_current = serializers.BooleanField()
    is_default = serializers.BooleanField()
    is_success = serializers.BooleanField()
    is_failed = serializers.BooleanField()
    invitations = serializers.SerializerMethodField()

    def get_invitations(self, obj):
        step_entries = obj.get("invitations", [])
        latest_invitation_id = obj.get("latest_invitation_id")
        latest_sub_id = obj.get("latest_sub_id")

        if not step_entries:
            return []

        result = []
        for entry in step_entries:
            main = entry["main"]
            subs = entry["subs"]  # ordered by -create_date

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
