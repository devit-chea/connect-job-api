from logging import getLogger

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.auth_totp_mail.exceptions import ExpiredError
from apps.auth_totp_mail.utils import commons
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.abstract_model import AbstractBaseCompany
from apps.base.models.soft_delete_model import SoftDeleteModel
from apps.notification_app.services.notification_services import NotificationServices


COMPANY_MODEL = "base.Company"
AUTH_USER_MODEL = "auth_oauth.User"
logger = getLogger(__name__)

import logging

logger = logging.getLogger(__name__)


class EmailManager(models.Manager):
    def issue_email_otp(user_obj, request):
        """
        Create an email confirmation for `user_obj` and send a confirmation mail.

        The email will be directly saved to `auth_oauth_otp`
        """
        try:
            logger.info(f"Starting OTP issuance for user_id={user_obj.id} email={user_obj.email}")

            # generates a pseudo random code using os.urandom and binascii.hexlify
            confirmation_key = commons.generate_key_confirm()
            logger.debug(f"Generated confirmation key: {confirmation_key}")

            otp_instance = commons.generate_otp_instance(request)
            logger.debug(
                f"Generated OTP instance with expiry={otp_instance.otp_expiry}, "
                f"ip={otp_instance.ip_address}, user_agent={otp_instance.user_agent}"
            )

            # Delete previous OTPs for this user + company (cleanup)
            deleted_count, _ = TotpMailConfirmation.objects.filter(
                user=user_obj, company=user_obj.base_company
            ).delete()
            logger.info(f"Deleted {deleted_count} previous OTP(s) for user_id={user_obj.id}")

            totp_mail = TotpMailConfirmation.objects.create(
                user=user_obj,
                email=user_obj.email,
                send_at=timezone.now(),
                confirm_key=confirmation_key,
                company=user_obj.base_company,
                otp_expiry=otp_instance.otp_expiry,
                ip_address=otp_instance.ip_address,
                user_agent=otp_instance.user_agent,
                otp_encryption=otp_instance.otp_encrypted
            )
            logger.info(f"Created TotpMailConfirmation id={totp_mail.id} for user_id={user_obj.id}")

            template_context = commons.template_context(request, totp_mail, otp_instance.otp)
            totp_mail.send(template_context)
            logger.info(f"Sent OTP email for TotpMailConfirmation id={totp_mail.id}")

            return totp_mail

        except Exception as e:
            logger.error(f"Error issuing email OTP for user_id={user_obj.id}: {e}", exc_info=True)
            raise
    def issue_telegram_otp(user_obj, request):
        """
        Same as issue_email_otp but skips email send.
        Used for telegram/phone signups where email is not provided.
        """
        try:
            confirmation_key = commons.generate_key_confirm()
            otp_instance = commons.generate_otp_instance(request)

            TotpMailConfirmation.objects.filter(
                user=user_obj, company=user_obj.base_company
            ).delete()

            totp_mail = TotpMailConfirmation.objects.create(
                user=user_obj,
                email=None,
                send_at=timezone.now(),
                confirm_key=confirmation_key,
                company=user_obj.base_company,
                otp_expiry=otp_instance.otp_expiry,
                ip_address=otp_instance.ip_address,
                user_agent=otp_instance.user_agent,
                otp_encryption=otp_instance.otp_encrypted
            )

            return totp_mail, otp_instance.otp

        except Exception as e:
            logger.error(f"Error issuing telegram OTP for user_id={user_obj.id}: {e}", exc_info=True)
            raise

class TotpMailConfirmation(models.Model):
    """
    Once an email is confirmed, it will be delete from this table. In other words, there are only unconfirmed emails in the database.
    """
    ExpiredError = ExpiredError

    user = models.ForeignKey(
        AUTH_USER_MODEL,
        verbose_name=_("user"),
        on_delete=models.CASCADE,
        related_name='email_confirm_user'
    )

    company = models.ForeignKey(
        COMPANY_MODEL,
        on_delete=models.CASCADE,
        blank=True, null=True,
        editable=False,
        related_name='email_confirm_company')

    email = models.EmailField(verbose_name=_('Email'), db_index=True, null=True)
    confirm_key = models.TextField(_("Confirm Key"), max_length=64, db_index=True, unique=True, blank=False, null=False)
    otp_encryption = models.CharField(max_length=255, unique=True)
    otp_expiry = models.DateTimeField(blank=True, null=True)
    failed_confirm = models.IntegerField(default=0)
    create_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    send_at = models.DateTimeField(null=True, blank=True, db_index=True)
    confirmed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    ip_address = models.GenericIPAddressField(
        _("The IP address of this session"),
        default="",
        blank=True,
        null=True,
    )
    user_agent = models.CharField(
        max_length=512,
        verbose_name=_("HTTP User Agent"),
        default="",
        blank=True,
    )

    objects = EmailManager()

    class Meta:
        db_table = "auth_totp_mail"
        verbose_name = _('Email confirmation')
        verbose_name_plural = _('Email confirmation')

    def send(self, template_context=None):
        result = NotificationServices.send_email(
            self,
            template_context=template_context,
            subject_template_name_str='otp/login_confirm_subject.txt',
            body_template_name_str='otp/login_code_message.html'
        )
        logger.info(f"send result: {result}")

    def clean(self):
        """
        delete confirmation after verified
        """
        self.delete()

    def _otp_expiry(self):
        if not self.send_at:
            return False

        return self.otp_expiry <= timezone.now()

    def _failed_confirm(self):
        self.failed_confirm = int(self.failed_confirm) + 1
        self.save(update_fields=('failed_confirm',))


class MailTemplate(AbstractBaseModel, AbstractBaseCompany, SoftDeleteModel):
    """
    Reusable email template that can optionally be scoped to a company
    and/or attached to any object via Generic FK (content_type + object_id).
    """

    # core
    title = models.CharField(max_length=255, blank=True, default="")
    mail_from = models.CharField(max_length=255, blank=True, default="")  # allow "Name <email@x>"
    subject = models.CharField(max_length=255)  # NOT NULL in your table
    body = models.TextField()  # NOT NULL in your table (HTML or plain)
    specific_type = models.CharField(max_length=255, blank=True, default="")
    # e.g. "", "pipeline.success", "pipeline.failed", "pipeline.default"

    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False)
    description = models.CharField(max_length=512, null=True, blank=True)
    
    class Meta:
        db_table = "mail_template"
        indexes = [
            models.Index(fields=["company"]),
            models.Index(fields=["specific_type"]),
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return self.title or self.subject
