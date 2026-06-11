from rest_framework import serializers
from apps.base.decorators.datetime_format_decorator import (
    datetime_format_decorator,
    DateTimeFormat,
)
from apps.auth_totp_mail.models.invitation_models import Invitation
from apps.auth_totp_mail.utils.invitation_utils import RESCHEDULE, get_invitation_type_display


class InvitationListQuerySerializer(serializers.Serializer):
    pipeline_step_id = serializers.IntegerField()
    pipeline_config_id = serializers.IntegerField()


@datetime_format_decorator(
    fields=["invited_at"],
    field_formats={"invited_at": DateTimeFormat.DEFAULT},
    use_timezone=True,
)
class InvitationRescheduledChildSerializer(serializers.ModelSerializer):
    invitation_type_display = serializers.SerializerMethodField()
    is_latest = serializers.SerializerMethodField()
    recruiter = serializers.SerializerMethodField()
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
            "recruiter",
            "transaction_title",
        ]

    def get_invitation_type_display(self, obj):
        return get_invitation_type_display(obj.invitation_type)

    def get_is_latest(self, obj) -> bool:
        latest_id = self.context.get("latest_id")
        return obj.id == latest_id

    def get_recruiter(self, obj) -> dict | None:
        recruiter_map = self.context.get("recruiter_map", {})
        ucp_id = obj.create_ucp_id
        if ucp_id is None:
            return None
        return recruiter_map.get(int(ucp_id))

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
class ApplicationInvitationSummarySerializer(serializers.ModelSerializer):
    invitation_type_display = serializers.SerializerMethodField()
    is_latest = serializers.SerializerMethodField()
    transactions = serializers.SerializerMethodField()
    recruiter = serializers.SerializerMethodField()
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
            "recruiter",
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
            context={
                "latest_id": latest_id,
                "recruiter_map": self.context.get("recruiter_map", {}),  # pass down
            },
        ).data

    def get_recruiter(self, obj) -> dict | None:
        recruiter_map = self.context.get("recruiter_map", {})
        ucp_id = obj.create_ucp_id
        if ucp_id is None:
            return None
        return recruiter_map.get(int(ucp_id))

    def get_transaction_title(self, obj):
        latest_id = self.context.get("latest_id")
        if obj.id == latest_id:
            return RESCHEDULE
        return get_invitation_type_display(obj.invitation_type)