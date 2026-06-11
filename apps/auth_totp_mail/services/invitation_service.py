import re
import logging
from django.conf import settings
from types import SimpleNamespace
from unicodedata import normalize

from django.utils import timezone
from django.apps import apps as django_apps
from django.db import transaction
from django.template import Context, Template
from django.db.models.query import QuerySet

from apps.auth_totp_mail.constants.invite_type_contants import (
    InvitationStatus,
    InvitationType,
)
from apps.auth_totp_mail.models.invitation_models import Invitation
from apps.auth_totp_mail.models.mail_template_models import MailTemplate
from apps.auth_totp_mail.utils.invitation_utils import get_invitation_type_display
from apps.job_management_app.models.job_application_model import JobApplicationModel
from apps.notification_app.services.notification_services import NotificationServices

logger = logging.getLogger(__name__)


class InvitationService:

    # -------------------------------------------------------------------------
    # Private Helpers
    # -------------------------------------------------------------------------
    @staticmethod
    def _resolve_recipient_email(job_application: JobApplicationModel) -> str:
        applicant_email = getattr(job_application, "email", None)
        profile_email = getattr(job_application.profile, "email", None)

        recipient_mail = (
            applicant_email
            if applicant_email and applicant_email.strip()
            else profile_email
        )

        if not recipient_mail or not recipient_mail.strip():
            raise ValueError(
                "This applicant doesn't have email to receive invite notification."
            )

        return recipient_mail

    @staticmethod
    def _format_datetime(value: str) -> str:
        """Format a datetime object to '02 June 2026, 09:30 AM'"""
        if not value:
            return ""
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.strftime("%d %B %Y, %I:%M %p")

    @staticmethod
    def _generate_slug(text: str) -> str:
        """Generate a URL-friendly slug from a given text."""
        # Normalize unicode characters (e.g. accented letters → ASCII)
        text = normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        # Lowercase
        text = text.lower()
        # Replace any non-alphanumeric character (except hyphens) with a hyphen
        text = re.sub(r"[^a-z0-9]+", "-", text)
        # Strip leading/trailing hyphens
        text = text.strip("-")
        return text

    @staticmethod
    def _render_template(template_string: str, context: dict) -> str:
        """Render a Django template string with the given context."""
        try:
            return Template(template_string).render(Context(context))
        except Exception as exc:
            logger.warning("Template rendering failed: %s", exc)
            return template_string

    @staticmethod
    def _build_template_context(
        job_application: JobApplicationModel,
        invitation_type: str,
        additional_message: str = "",
        invited_at=None,
        location=None,
        metadata: dict = None,
        recruiter_name: str = "",
    ) -> dict:
        job_post = job_application.job_post
        job_id = getattr(job_post, "id", None)
        web_url = settings.WEB_BASE_URL
        job_title = getattr(job_post, "title", "")
        job_slug = getattr(job_post, "slug", None) or InvitationService._generate_slug(
            job_title
        )
        job_post_url = (
            "{}/en/jobs/{}-{}".format(web_url.rstrip("/"), job_slug, job_id)
            if job_slug and job_id
            else ""
        )
        job_application_url = (
            "{}/en/job-seeker/job-applied/{}".format(
                web_url.rstrip("/"), job_application.id
            )
            if job_application.id
            else ""
        )

        return {
            "applicant_name": job_application.applicant_name,
            "applicant_email": job_application.email,
            "job_title": getattr(job_application.job_post, "title", ""),
            "company_name": getattr(job_application.job_post.company, "name", ""),
            "invitation_type": invitation_type,
            "additional_message": additional_message,
            "invited_at": invited_at,
            "location": location,
            "metadata": metadata or {},
            "recruiter_name": recruiter_name,
            "job_post_url": job_post_url,
            "job_application_url": job_application_url,
        }

    @staticmethod
    def _get_company_id(job_application: JobApplicationModel) -> int | None:
        job = getattr(job_application, "job_post", None)
        company = getattr(job, "company", None)
        return getattr(company, "id", None)

    @staticmethod
    def _resolve_sender_instance(job_application: JobApplicationModel, company_id):
        """Return an object with company_id for the notification sender."""
        if getattr(job_application, "company_id", None):
            return job_application
        return SimpleNamespace(company_id=company_id)

    # -------------------------------------------------------------------------
    # Public Interface
    # -------------------------------------------------------------------------

    @classmethod
    @transaction.atomic
    def send_invitation(
        cls,
        *,
        validated_data: dict,
        job_application: JobApplicationModel,
        mail_template: MailTemplate,
        company_id,
        ucp,
        pipeline_config,
        pipeline_step,
    ) -> Invitation:

        recipient_mail = cls._resolve_recipient_email(job_application)

        recruiter_name = ucp.profile.full_name
        invitation_type = validated_data["invitation_type"]

        context = cls._build_template_context(
            job_application,
            invitation_type=get_invitation_type_display(invitation_type),
            additional_message=validated_data.get("additional_message", ""),
            invited_at=cls._format_datetime(validated_data.get("invited_at")),
            location=validated_data.get("location"),
            metadata=validated_data.get("metadata", {}),
            recruiter_name=recruiter_name,
        )

        invitation = Invitation.objects.create(
            job_application=job_application,
            mail_template=mail_template,
            invitation_type=invitation_type,
            subject_snapshot=cls._render_template(mail_template.subject, context),
            body_snapshot=cls._render_template(mail_template.body, context),
            status=InvitationStatus.PENDING,
            additional_message=validated_data.get("additional_message", ""),
            location=validated_data.get("location"),
            latitude=validated_data.get("latitude"),
            longitude=validated_data.get("longitude"),
            metadata=validated_data.get("metadata", {}),
            company_id=company_id,
            create_ucp_id=validated_data["create_ucp_id"],
            create_uid=validated_data["create_uid"],
            invited_at=validated_data.get("invited_at"),
            pipeline_config=pipeline_config,
            pipeline_step=pipeline_step,
        )

        mail_template_id = validated_data.get("mail_template_id")

        cls._dispatch_email(
            invitation,
            job_application,
            recruiter_name,
            mail_template_id,
            context=context,  # pass the already-built context
            recipient_mail=recipient_mail,
        )
        return invitation

    # -------------------------------------------------------------------------
    # Email Dispatch
    # -------------------------------------------------------------------------

    @classmethod
    def _dispatch_email(
        cls,
        invitation: Invitation,
        job_application: JobApplicationModel,
        recruiter_name: str = "",
        mail_template_id: int = None,
        context: dict = None,
        recipient_mail: str = None,
    ) -> None:
        company_id = cls._get_company_id(job_application)

        if not mail_template_id:
            logger.warning("Email Dispatch: Mail Template ID not found.")
            return

        mail_template = MailTemplate.objects.filter(id=mail_template_id).first()

        if not mail_template:
            logger.warning(
                "Email not sent: MailTemplate for type '%s' not found.",
                invitation.invitation_type,
            )

        template_context = {
            "user_id": getattr(job_application, "create_uid", None)
            or getattr(job_application, "write_uid", None),
            "recipient": recipient_mail,
            "applicant_name": job_application.applicant_name,
            "job_title": getattr(job_application.job_post, "title", ""),
            "company_name": getattr(
                job_application.job_post.company, "name", "the company"
            ),
            "location": (
                invitation.location
                or getattr(job_application.job_post.company, "address", None)
                or "No location provided"
            ),
            "invited_at": invitation.invited_at,
            "invitation_type": (
                InvitationType(invitation.invitation_type).label
                if invitation.invitation_type
                else ""
            ),
            "additional_message": invitation.additional_message,
            "recruiter_name": recruiter_name,
            # merge pre-built context last so job_post_url & job_application_url are included
            **(context or {}),
        }

        try:
            logger.info(
                "Sending invitation email to '%s'.",
                job_application.email,
            )
            NotificationServices.send_email_from_db_template(
                cls._resolve_sender_instance(job_application, company_id),
                template_id=mail_template.id,
                template_context=template_context,
                send_type=invitation.invitation_type,
                channels=["email"],
                force_send=True,
            )
            invitation.status = InvitationStatus.SENT

        except Exception as exc:
            logger.exception(
                "Failed to send invitation email to '%s': %s",
                job_application.email,
                exc,
            )
            invitation.status = InvitationStatus.FAILED
            raise

        finally:
            invitation.save(update_fields=["status"])

    @staticmethod
    def get_invitation_history(
        *, job_application_id: str, company_id, filters: dict
    ) -> QuerySet:
        queryset = (
            Invitation.objects.filter(
                job_application_id=job_application_id,
                company_id=company_id,
            )
            .select_related("mail_template", "job_application")
            .order_by("-create_date")
        )

        if filters.get("status"):
            queryset = queryset.filter(status=filters["status"])

        if filters.get("invitation_type"):
            queryset = queryset.filter(invitation_type=filters["invitation_type"])

        return queryset

    @classmethod
    @transaction.atomic
    def reschedule_invitation(
        cls, *, invitation: Invitation, validated_data: dict, ucp
    ) -> Invitation:
        recruiter_name = ucp.profile.full_name

        recipient_mail = cls._resolve_recipient_email(invitation.job_application)

        # Use newly provided template or fall back to existing one
        new_template = (
            validated_data.pop("_mail_template", None) or invitation.mail_template
        )
        invitation_type = validated_data.get(
            "invitation_type", invitation.invitation_type
        )
        additional_message = validated_data.get(
            "additional_message", invitation.additional_message
        )
        invited_at = cls._format_datetime(
            validated_data.get("invited_at", invitation.invited_at)
        )
        location = validated_data.get("location", invitation.location)
        metadata = validated_data.get("metadata", invitation.metadata)

        # Re-render subject and body if template or invitation_type changed
        if new_template:
            context = cls._build_template_context(
                invitation.job_application,
                get_invitation_type_display(invitation_type),
                additional_message,
                invited_at,
                location,
                metadata,
                recruiter_name,
            )
            subject = cls._render_template(new_template.subject, context)
            body = cls._render_template(new_template.body, context)
        else:
            subject = invitation.subject_snapshot
            body = invitation.body_snapshot

        # Mark original invitation as rescheduled
        invitation.is_rescheduled = True
        invitation.status = InvitationStatus.CANCELLED
        invitation.save(update_fields=["is_rescheduled", "status"])

        # Create new invitation row linked back to original
        new_invitation = Invitation.objects.create(
            # Link to original
            rescheduled_from=invitation,
            # Carry over from original
            job_application=invitation.job_application,
            company=invitation.company,
            pipeline_config=invitation.pipeline_config,
            pipeline_step=invitation.pipeline_step,
            # Updated fields
            mail_template=new_template,
            invitation_type=invitation_type,
            subject_snapshot=subject,
            body_snapshot=body,
            additional_message=additional_message,
            location=validated_data.get("location", invitation.location),
            latitude=validated_data.get("latitude", invitation.latitude),
            longitude=validated_data.get("longitude", invitation.longitude),
            invited_at=validated_data.get("invited_at", invitation.invited_at),
            metadata=validated_data.get("metadata", invitation.metadata),
            status=InvitationStatus.PENDING,
            is_rescheduled=False,
            write_ucp_id=validated_data["write_ucp_id"],
            write_uid=validated_data["write_uid"],
            create_ucp_id=validated_data["create_ucp_id"],
            create_uid=validated_data["create_uid"],
        )

        # Re-send email with updated content mail_template_id
        cls._dispatch_email(
            invitation=new_invitation,
            job_application=new_invitation.job_application,
            recruiter_name=recruiter_name,
            mail_template_id=validated_data.get(
                "mail_template_id", new_invitation.mail_template_id
            ),
            context=context,
            recipient_mail=recipient_mail,
        )

        return new_invitation

    @staticmethod
    @transaction.atomic
    def update_invitation_status(
        *, invitation: Invitation, validated_data: dict
    ) -> Invitation:
        new_status = validated_data["status"]

        # Guard invalid transitions
        IMMUTABLE_STATUSES = [InvitationStatus.CANCELLED, InvitationStatus.DONE]
        if invitation.status in IMMUTABLE_STATUSES:
            raise ValueError(
                f"Cannot update status of an invitation that is already {invitation.status}."
            )

        invitation.status = new_status
        invitation.write_ucp_id = validated_data["write_ucp_id"]
        invitation.write_uid = validated_data["write_uid"]
        invitation.save(update_fields=["status", "write_ucp_id", "write_uid"])

        return invitation

    @staticmethod
    def get_upcoming_events(*, ucp, filters: dict) -> QuerySet:
        now = timezone.now()
        ucp_id = ucp.id

        queryset = (
            Invitation.objects.filter(
                job_application__create_ucp_id=ucp_id,
                invited_at__gte=now,
                status__in=[InvitationStatus.SENT, InvitationStatus.PENDING],
            )
            .select_related(
                "mail_template",
                "job_application",
                "job_application__job_post",
                "job_application__job_post__company",
            )
            .order_by("invited_at")
        )

        # Filter by status
        if filters.get("status"):
            queryset = queryset.filter(status=filters["status"])

        # Filter by date range
        if filters.get("invited_at_from"):
            queryset = queryset.filter(invited_at__gte=filters["invited_at_from"])

        if filters.get("invited_at_to"):
            queryset = queryset.filter(invited_at__lte=filters["invited_at_to"])

        # Search by job title (case-insensitive)
        if filters.get("job_title"):
            queryset = queryset.filter(
                job_application__job_post__title__icontains=filters["job_title"]
            )

        # Exclude any invitation that is pointed to by another invitation
        # (i.e. it has been rescheduled — a newer one exists in the chain)
        # Only keep the latest in each chain = not referenced by anyone as rescheduled_from_id
        all_ids = queryset.values_list("id", flat=True)
        referenced_ids = Invitation.objects.filter(
            rescheduled_from_id__in=all_ids,
        ).values_list("rescheduled_from_id", flat=True)

        return queryset.exclude(id__in=referenced_ids)
