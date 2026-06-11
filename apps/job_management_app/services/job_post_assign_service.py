from __future__ import annotations

import logging
from types import SimpleNamespace

from django.apps import apps as django_apps
from django.db import transaction

logger = logging.getLogger(__name__)

ASSIGN_MAIL_TEMPLATE_TYPE = "job.recruiter.assigned"


class JobPostAssignNotificationService:
    """
    Sends an email notification to a recruiter when they are assigned to a job post.
    """

    @staticmethod
    def notify_assigned(assignment, job_post, assigner_profile) -> bool:
        from apps.notification_app.services.notification_services import NotificationServices

        MailTemplate = django_apps.get_model("auth_totp_mail", "MailTemplate")

        try:
            mail_template = MailTemplate.objects.filter(
                specific_type=ASSIGN_MAIL_TEMPLATE_TYPE,
            ).first()
        except Exception:
            logger.warning("MailTemplate '%s' query failed.", ASSIGN_MAIL_TEMPLATE_TYPE)
            return False

        if not mail_template:
            logger.warning(
                "Email not sent: MailTemplate '%s' not found in DB. "
                "Create one with specific_type='%s'.",
                ASSIGN_MAIL_TEMPLATE_TYPE,
                ASSIGN_MAIL_TEMPLATE_TYPE,
            )
            return False

        ucp = assignment.assigned_ucp
        profile = getattr(ucp, "profile", None)
        recipient_email = getattr(profile, "email", None)
        user_id = getattr(ucp, "user_id", None)

        if not recipient_email or not user_id:
            logger.warning(
                "Email not sent: assigned recruiter (ucp_id=%s) has no email or user_id.",
                getattr(ucp, "id", None),
            )
            return False

        company = getattr(job_post, "company", None)
        template_context = {
            "user_id": user_id,
            "recipient": recipient_email,
            "recruiter_name": getattr(profile, "full_name", None) or recipient_email.split("@")[0],
            "assigned_by_name": getattr(assigner_profile, "full_name", None) or "A recruiter",
            "job_title": getattr(job_post, "title", "the position"),
            "company_name": getattr(company, "name", "the company") if company else "the company",
            "job_id": job_post.id,
        }

        template_id = mail_template.id
        instance_for_sender = SimpleNamespace(
            company_id=getattr(job_post, "company_id", None)
        )

        def _dispatch():
            NotificationServices.send_email_from_db_template_v1(
                instance_for_sender,
                template_id=template_id,
                template_context=template_context,
            )

        transaction.on_commit(_dispatch)
        return True