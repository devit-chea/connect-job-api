import logging

from apps.auth_totp_mail.models.mail_template_models import MailTemplate
from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.views.base_views import (
    AdminRecruiterOrRecruiterBaseViewSet,
)
from apps.auth_totp_mail.serializers.mail_template_serializers import (
    MailTemplateConfigListSerializer,
    MailTemplateConfigSerializer,
    MailTemplateRetrieveSerializer,
    MailTemplateCreateUpdateSerializer,
)

logger = logging.getLogger(__name__)


class MailTemplateConfigViewSet(PermissionMixin, AdminRecruiterOrRecruiterBaseViewSet):
    queryset = MailTemplate.objects.all()
    serializer_class = MailTemplateConfigSerializer
    permission_codename = [
        "admin_recruiter_manage_job_post",
        "recruiter_manage_job_post",
    ]
    ordering = ["-id"]
    search_fields = ["title", "subject"]
    ordering_fields = ["id", "create_date", "write_date"]

    def get_serializer_class(self):
        if self.action == "list":
            return MailTemplateConfigListSerializer
        if self.action == "retrieve":
            return MailTemplateRetrieveSerializer
        if self.action in ["create", "update"]:
            return MailTemplateCreateUpdateSerializer
        return MailTemplateConfigSerializer
