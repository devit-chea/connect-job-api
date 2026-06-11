from django import forms
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from apps.auth_totp_mail.constants.mail_type_constants import MailSpecificTypes
from apps.auth_totp_mail.models.mail_template_models import (
    MailTemplate,
    TotpMailConfirmation,
)
from apps.auth_totp_mail.utils.convert_mention_template import (
    convert_django_template_to_mention,
    convert_mention_to_django_template,
)
from apps.base.decorators.datetime_format_decorator import (
    datetime_format_decorator,
    DateTimeFormat,
)


class ConfirmSerializers(serializers.Serializer):
    confirm_key = serializers.CharField(write_only=True)
    otp_encrypted = serializers.CharField(write_only=True)
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class ResendOtpForm(forms.Form):
    def __init__(self, *args):
        super().__init__(*args)
        self.fields["confirm_key"].required = True

    confirm_key = forms.CharField(required=False)


class ResendSerializers(serializers.Serializer):
    confirm_key = serializers.CharField(write_only=True)


class LoginResendSerializers(serializers.Serializer):
    username = serializers.CharField(write_only=True)


class ContentTypeBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentType
        fields = ("id", "app_label", "model")


class MailTemplateWriteSerializer(serializers.ModelSerializer):
    content_type = serializers.PrimaryKeyRelatedField(
        queryset=ContentType.objects.all(), allow_null=True, required=False
    )

    class Meta:
        model = MailTemplate
        fields = (
            "id",
            "title",
            "mail_from",
            "subject",
            "body",
            "specific_type",
            "company",
            "content_type",
            "object_id",
        )

    def validate(self, attrs):
        if not attrs.get("subject"):
            raise serializers.ValidationError({"subject": "Subject is required."})
        if not attrs.get("body"):
            raise serializers.ValidationError({"body": "Body is required."})
        return attrs


class MailTemplateReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = MailTemplate
        fields = (
            "id",
            "specific_type",
            "company",
            "title",
        )


class MailTemplateConfigSerializer(serializers.ModelSerializer):
    company_id = serializers.IntegerField()

    class Meta:
        model = MailTemplate
        fields = (
            "id",
            "title",
            "mail_from",
            "subject",
            "body",
            "specific_type",
            "company",
            "content_type",
            "object_id",
            "is_active",
            "company_id",
            "description",
        )

    def validate_specific_type(self, value):
        if value is not None and value not in MailSpecificTypes.values:
            raise serializers.ValidationError("Invalid specific type selected.")
        return value

    def to_internal_value(self, data):
        request = self.context.get("request", None)
        company_id = getattr(request, "company_id", None)
        data["company_id"] = company_id

        return super().to_internal_value(data)


@datetime_format_decorator(
    fields=["create_date", "write_date"],
    field_formats={"post_date": DateTimeFormat.DEFAULT},
    use_timezone=True,
)
class MailTemplateConfigListSerializer(serializers.ModelSerializer):
    class Meta:
        model = MailTemplate
        fields = (
            "id",
            "title",
            "mail_from",
            "subject",
            "object_id",
            "is_active",
            "description",
            "create_date",
            "write_date",
        )


class MailTemplateRetrieveSerializer(serializers.ModelSerializer):
    body = serializers.SerializerMethodField()
    subject = serializers.SerializerMethodField()

    def get_body(self, obj):
        return convert_django_template_to_mention(obj.body or "")
    
    def get_subject(self, obj):
        return convert_django_template_to_mention(obj.subject or "")

    class Meta:
        model = MailTemplate
        fields = (
            "id",
            "title",
            "mail_from",
            "subject",
            "body",
            "specific_type",
            "company",
            "content_type",
            "object_id",
            "is_active",
            "company_id",
            "description",
            "create_date",
        )


class MailTemplateCreateUpdateSerializer(serializers.ModelSerializer):
    company_id = serializers.IntegerField()

    def validate_body(self, value):
        return convert_mention_to_django_template(value or "")
    
    def validate_subject(self, value):
        return convert_mention_to_django_template(value or "")

    class Meta:
        model = MailTemplate
        fields = (
            "id",
            "title",
            "mail_from",
            "subject",
            "body",
            "specific_type",
            "company",
            "content_type",
            "object_id",
            "is_active",
            "company_id",
            "description",
        )

    def to_internal_value(self, data):
        request = self.context.get("request", None)
        company_id = getattr(request, "company_id", None)
        data["company_id"] = company_id

        return super().to_internal_value(data)
