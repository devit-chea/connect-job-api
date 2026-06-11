from django.db import models
from django.utils.translation import gettext_lazy as _

COMPANY_MODEL = "base.Company"
AUTH_USER_MODEL = "auth_oauth.User"
APP_CHOICES = [
    ("auth_totp_mail", "AUTH TOTP MAIL"),
    ("auth_totp_mfa", "AUTH TOTP MFA")
]

class AuthSettingModel(models.Model):
    create_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    write_date = models.DateTimeField(auto_now=True, blank=True, null=True)
    create_uid = models.IntegerField(blank=True, null=True, editable=False)
    write_uid = models.IntegerField(blank=True, null=True, editable=False)

    user = models.ForeignKey(
        AUTH_USER_MODEL,
        verbose_name=_("user"),
        on_delete=models.CASCADE,
        related_name='auth_setting_user'
    )
    company = models.ForeignKey(
        COMPANY_MODEL,
        on_delete=models.CASCADE, 
        blank=True, null=True,
        editable=False,
        related_name='auth_setting_company')
    
    app_name = models.CharField(max_length=100, choices=APP_CHOICES, default='auth_totp_mail', null=True, blank=True)
    is_enable = models.BooleanField(default=False)

    class Meta:
        db_table = "auth_setting"
        verbose_name = _('Auth Setting')
        verbose_name_plural = _('Auth Setting')
        unique_together = ['user', 'company', 'app_name']
