from rest_framework import serializers

from apps.auth_oauth.constants.auth_constants import AuthenticationProviders


class SocialSerializer(serializers.Serializer):
    provider = serializers.CharField()
    code = serializers.CharField()


class MobileGoogleSerializer(serializers.Serializer):
    token = serializers.CharField()
    id_token = serializers.CharField()
    user_type = serializers.ChoiceField(
        choices=['applicant'],
        required=False,
        allow_null=True,
        allow_blank=True
    )


class MobileLinkedInSerializer(serializers.Serializer):
    code = serializers.CharField()
    user_type = serializers.ChoiceField(
        choices=['applicant'],
        required=False,
        allow_null=True,
        allow_blank=True
    )
class MobileAppleSerializer(serializers.Serializer):
    code = serializers.CharField()
    user_type = serializers.ChoiceField(
        choices=['applicant'],
        required=False,
        allow_null=True,
        allow_blank=True
    )

class GoogleCallbackSerializer(serializers.Serializer):
    pass


class LinkedinCallbackSerializer(serializers.Serializer):
    pass


class UserAuthenticationRedirectUrlSerializer(serializers.Serializer):
    provider_name = serializers.ChoiceField(choices=AuthenticationProviders.choices)

class TelegramCallbackSerializer(serializers.Serializer):
    code = serializers.CharField()
    code_verifier = serializers.CharField()