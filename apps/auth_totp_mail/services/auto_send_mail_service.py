from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Optional, Dict, Any

from django.apps import apps as django_apps
from django.db import transaction
from django.utils import timezone

from apps.auth_oauth.models.profile_model import Profile
from apps.job_management_app.models.job_application_model import JobApplicationModel
from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineStatusConfigModel,
    JobPipelineStepPropertyDefaultConfigModel,
    JobPipelineConfigStepModel,
)
from apps.notification_app.services.notification_services import NotificationServices

logger = logging.getLogger(__name__)


class AutoSendMailService:
    @staticmethod
    def trigger_for_status(
        application: JobApplicationModel,
        new_status: JobPipelineStatusConfigModel,
        pipeline_step: JobPipelineConfigStepModel,
        recruiter_profile_id=None,
    ) -> bool:
        """
        If the current step’s defaults say this status should auto-send,
        render the DB template (via NotificationServices) AFTER commit.
        """
        if not AutoSendMailService._is_send(application, new_status):
            return False

        step_property = (
            JobPipelineStepPropertyDefaultConfigModel.objects.select_related(
                "success_mail_template_id", "failed_mail_template_id"
            )
            .filter(step=pipeline_step)
            .first()
        )
        if not step_property:
            return False

        template_id = AutoSendMailService._pick_template_id(step_property, new_status)
        if not template_id:
            return False

        mail_ctx = AutoSendMailService._build_mailer_context(
            application, new_status, recruiter_profile_id
        )
        if not (mail_ctx.get("user_id") and mail_ctx.get("recipient")):
            return False

        company_id = getattr(application.job_post, "company_id", None)
        instance_for_sender = (
            application
            if getattr(application, "company_id", None)
            else SimpleNamespace(company_id=company_id)
        )

        def _dispatch():
            logger.warning(f"Mail Template ID: {template_id.id}")
            NotificationServices.send_email_from_db_template_v1(
                instance_for_sender,
                template_id=template_id.id,
                template_context=mail_ctx,
            )

        transaction.on_commit(_dispatch)
        return True

    @staticmethod
    def _is_send(
        application: JobApplicationModel,
        new_status: Optional[JobPipelineStatusConfigModel],
    ) -> bool:
        return bool(
            application
            and new_status
            and application.email
            and application.pipeline_step
        )

    @staticmethod
    def _pick_template_id(
        step_prop: JobPipelineStepPropertyDefaultConfigModel,
        new_status: JobPipelineStatusConfigModel,
    ) -> Optional[int]:
        if (
            step_prop.is_success_auto_send
            and step_prop.success_mail_template_id
            and new_status.id == step_prop.success_status_id
        ):
            return step_prop.success_mail_template_id
        if (
            step_prop.is_failed_auto_send
            and step_prop.failed_mail_template_id
            and new_status.id == step_prop.failed_status_id
        ):
            return step_prop.failed_mail_template_id
        return None

    @staticmethod
    def _build_mailer_context(
        application: JobApplicationModel,
        new_status: JobPipelineStatusConfigModel,
        recruiter_profile_id=None,
    ) -> Dict[str, Any]:
        job = application.job_post
        company = getattr(job, "company", None)

        recruiter_name = ""
        if recruiter_profile_id:
            recruiter_name = (
                Profile.objects.filter(id=recruiter_profile_id)
                .values_list("full_name", flat=True)
                .first()
                or ""
            )
        user_id = getattr(application, "create_uid", None) or getattr(
            application, "write_uid", None
        )

        return {
            "now": timezone.now(),
            "user_id": user_id,
            "recipient": application.email,
            "application_id": application.id,
            "candidate_name": application.applicant_name
            or application.email
            or "Candidate",
            "candidate_email": application.email,
            "job": {"id": job.id, "title": getattr(job, "title", None)},
            "company_id": getattr(job, "company_id", None),
            "company_name": getattr(company, "name", None) if company else None,
            "recruiter_name": recruiter_name,
            "pipeline": {
                "step": {
                    "id": getattr(application.pipeline_step, "id", None),
                    "name": application.pipeline_step_name
                    or getattr(application.pipeline_step, "name", None),
                },
                "status": {
                    "id": getattr(new_status, "id", None),
                    "name": application.pipeline_status_name
                    or getattr(new_status, "name", None),
                },
            },
            "applicant_name": application.applicant_name,
            "email": application.email,
            "invited_at": timezone.now(),
            "location":  getattr(company, "address", None) if company else None,
            "job_title": getattr(job, "title", None),
        }


class ApplicationSubmitService:
    """
    Send email on applicant submit, using a DB MailTemplate.
    """

    @staticmethod
    def send_confirmation(application):
        """
        :param application: JobApplicationModel instance
        """
        MailTemplate = django_apps.get_model("auth_totp_mail", "MailTemplate")
        try:
            mail_template = MailTemplate.objects.filter(
                specific_type="application.submit",
            ).first()
        except MailTemplate.DoesNotExist:
            logger.warning("Email not sent: MailTemplate 'JOB_APPLIED' not found")
            return False
        if not application or not application.email or not mail_template:
            logger.warning(
                "Email not sent: MailTemplate 'JOB_APPLIED' recipient email not found."
            )
            return False

        template_id = mail_template.id
        job = getattr(application, "job_post", None)
        company = getattr(job, "company", None)

        applicant_name = (
            getattr(application, "applicant_name", None)
            or application.email.split("@")[0]
            or "Applicant"
        )

        # Template context
        template_context = {
            "user_id": getattr(application, "create_uid", None)
            or getattr(application, "write_uid", None),
            "recipient": application.email,
            "applicant_name": applicant_name,
            "job_title": getattr(job, "title", "the position"),
            "company_name": getattr(company, "name", "the company"),
        }

        if not template_context["user_id"] or not template_context["recipient"]:
            logger.warning(
                "Email not sent: MailTemplate 'JOB_APPLIED' recipient email not found(user_id none)"
            )
            return False

        company_id = getattr(company, "id", None)
        instance_for_sender = (
            application
            if getattr(application, "company_id", None)
            else SimpleNamespace(company_id=company_id)
        )

        def _dispatch():
            NotificationServices.send_email_from_db_template_v1(
                instance_for_sender,
                template_id=template_id,
                template_context=template_context,
            )

        transaction.on_commit(_dispatch)
        return True
