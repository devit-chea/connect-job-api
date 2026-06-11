from datetime import datetime, timedelta

from django.contrib import auth
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Q
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django_rest_passwordreset.signals import reset_password_token_created
from environs import env

from apps.auth_oauth.constants.auth_constants import UserStatus, UserState
from apps.auth_oauth.services.send_email_service import EmailService
from apps.base.constants.base_constants import ENV
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.company_model import Company
from apps.base.utils.base_util import password_generator
from apps.core.exceptions.base_exceptions import BadRequestException
from apps.notification_app.services.notification_services import NotificationServices
from config.celery import app
from config.settings.base import IS_SEND_DEFAULT_PASSWORD

env.read_env()


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):

        email = self.normalize_email(email)
        existed_user = (self.model).objects.filter(
            email=email, status=UserStatus.ACTIVE, is_active=True
        )
        if existed_user.exists():
            return existed_user.order_by("-id").first()
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser has to have is_staff being True")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser has to have is_superuser being True")

        return self.create_user(email=email, password=password, **extra_fields)

    def get_by_natural_key(self, username):

        return self.filter(
            **{
                self.model.USERNAME_FIELD: username,
                "status": UserStatus.ACTIVE,
                "is_active": True,
            }
        ).first()


class User(AbstractUser, AbstractBaseModel):
    password = models.CharField(_("password"), max_length=512)
    username_validator = UnicodeUsernameValidator()
    username = models.CharField(
        _("username"),
        max_length=150,
        help_text=_(
            "Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
        ),
        validators=[username_validator],
    )
    email = models.EmailField(blank=True, null=True)
    login_type = models.CharField(max_length=50, default="pwd")
    count_fail = models.IntegerField(blank=True, null=True)
    last_fail = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, blank=True, default="active")
    password_expired = models.DateTimeField(default=datetime.now)
    base_company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        parent_link=True,
        related_name="current_company",
        blank=True,
        null=True,
    )
    company = models.ManyToManyField(
        Company,
        blank=True,
        verbose_name="list of companies",
        related_name="companies",
    )
    objects = UserManager()
    is_send_email = models.BooleanField(default=False)
    is_password_lock = models.BooleanField(default=False)
    is_password_expired = models.BooleanField(default=False)
    is_lock = models.BooleanField(default=False)
    is_expired = models.BooleanField(default=False)
    is_disable = models.BooleanField(default=False)
    is_two_step_verification = models.BooleanField(default=False)
    state = models.CharField(max_length=50, blank=True, null=True)
    number_of_created = models.IntegerField(default=1)
    is_login = models.BooleanField(default=False)
    is_required_reset_pwd = models.BooleanField(default=False)
    otp_sent_count = models.PositiveIntegerField(default=0)
    default_password = models.TextField(blank=True, null=True)
    default_user_profile_company = models.IntegerField(blank=True, null=True)
    otp_reset = models.DateTimeField(default=datetime.now)
    is_pending_verification = models.BooleanField(default=False)
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )
    telegram_chat_id = models.CharField(
        max_length=255, null=True, blank=True,
    )
    telegram_link_token = models.CharField(max_length=100, null=True, blank=True)
    def __str__(self):
        return self.username

    class Meta:
        app_label = "auth_oauth"
        description = "User"

    def has_perm(self, perm, obj=None, menu_path=None):
        return self._user_has_perm(self, perm, obj=obj, menu_path=menu_path)

    def _user_has_perm(self, user, perm, obj, menu_path=None):
        """
        A backend can raise `PermissionDenied` to short-circuit permission checking.
        """
        for backend in auth.get_backends():
            if not hasattr(backend, "has_perm"):
                continue
            try:
                if backend.has_perm(user, perm, obj, menu_path):
                    return True
            except PermissionDenied:
                return False
        return False


"""
This function is used to:
1. Allow user to sign up without verifying with existing username or email
2. Allow with Dev environment only
3. Trigger environment variable from .env file
"""


@receiver(pre_save, sender=User)
def validate_user(sender, instance, **kwargs):
    if instance.is_login or env.str("DJANGO_ENV") == ENV.DEV:
        return

    # google mobile
    if instance.id and instance.social_auth.filter(user=instance).exists():
        return

    user_query = sender.objects.filter(
        Q(~Q(state=UserState.PENDING_VERIFY_OPT), status=UserStatus.ACTIVE)
        | Q(state=UserState.PENDING_VERIFY_OPT, is_required_reset_pwd=True,status=UserStatus.ACTIVE)
    )
    existed_user = user_query.filter(username=instance.username).exists()
    existed_email = user_query.filter(email=instance.email).exists()
    existed_user_msg = "Unable to create the account."
    if existed_user:
        raise BadRequestException(existed_user_msg)
    if existed_email:
        raise BadRequestException(existed_user_msg)


@receiver(post_save, sender=User)
def update_pwd_auth2(sender, instance, **kwargs):
    if (
        instance.id
        and instance.social_auth.filter(user=instance).exists()
        and not instance.is_login
    ):
        default_password = password_generator(length=8)
        hash_password = make_password(default_password)
        sender.objects.filter(pk=instance.id).update(
            is_required_reset_pwd=True, password=hash_password
        )
        if IS_SEND_DEFAULT_PASSWORD:
            template_context = EmailService().template_context(
                user=instance, default_password=default_password
            )
            EmailService().send_default_password(instance, template_context)


class CustomPasswordReset:
    @receiver(reset_password_token_created)
    def password_reset_token_created(
        sender, instance, reset_password_token, request, *args, **kwargs
    ):
        from apps.auth_setting.config import Configs
        from apps.auth_oauth.utils.reset_password_context import (
            reset_pass_template_context,
        )

        template_context = reset_pass_template_context(request, reset_password_token)

        NotificationServices.send_email(
            instance,
            template_context=template_context,
            subject_template_name_str="auth_totp_mail/reset_password/reset_password_subject.txt",
            body_template_name_str="auth_totp_mail/reset_password/reset_password_message.html",
        )
