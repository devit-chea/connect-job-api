from django.db import models

from apps.auth_totp_mail.constants.invite_type_contants import (
    InvitationStatus,
    InvitationType,
)
from apps.auth_totp_mail.models.mail_template_models import MailTemplate
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.abstract_model import AbstractBaseCompany
from apps.base.models.soft_delete_model import SoftDeleteModel
from apps.job_management_app.models.job_application_model import JobApplicationModel
from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineConfigModel,
    JobPipelineConfigStepModel,
)


class Invitation(AbstractBaseModel, AbstractBaseCompany, SoftDeleteModel):

    job_application = models.ForeignKey(
        JobApplicationModel,
        on_delete=models.CASCADE,
        null=True,
        related_name="invitations",
    )
    mail_template = models.ForeignKey(
        MailTemplate, on_delete=models.SET_NULL, null=True, related_name="invitations"
    )
    invitation_type = models.CharField(
        max_length=20, choices=InvitationType.choices, db_index=True
    )

    # Snapshot (CRITICAL)
    subject_snapshot = models.CharField(max_length=500)
    body_snapshot = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
        db_index=True,
    )
    invited_at = models.DateTimeField(blank=True, null=True)
    additional_message = models.CharField(max_length=512, blank=True, null=True)
    location = models.CharField(max_length=512, blank=True, null=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        help_text="Geographic latitude (precision: 6 decimal places)",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        help_text="Geographic longitude (precision: 6 decimal places)",
    )
    # Dynamic data (interview time, links, etc.)
    metadata = models.JSONField(default=dict, blank=True)

    pipeline_config = models.ForeignKey(
        JobPipelineConfigModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations",
    )
    pipeline_step = models.ForeignKey(
        JobPipelineConfigStepModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations",
    )
    rescheduled_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reschedules",  # invitation.reschedules.all() = all reschedule children
    )
    is_rescheduled = models.BooleanField(default=False)  # flag original as rescheduled

    class Meta:
        db_table = "invitations"
        indexes = [
            models.Index(fields=["job_application", "invitation_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["pipeline_config", "pipeline_step"]),
            models.Index(fields=["rescheduled_from"]),
        ]

    def __str__(self):
        return f"Invitation #{self.id} - {self.invitation_type}"
