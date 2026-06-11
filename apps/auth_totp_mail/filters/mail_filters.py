import django_filters

from apps.auth_totp_mail.models.mail_template_models import MailTemplate

class MailTemplateFilter(django_filters.FilterSet):
    specific_type = django_filters.CharFilter()
    specific_type__in = django_filters.BaseInFilter(
        field_name="specific_type",
        lookup_expr="in"
    )

    class Meta:
        model = MailTemplate
        fields = ["specific_type"]