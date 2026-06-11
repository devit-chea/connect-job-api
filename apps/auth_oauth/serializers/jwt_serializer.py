from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from django.contrib.auth.models import update_last_login
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.utils import datetime_from_epoch

from apps.auth_oauth.models.auth_models import User
from apps.core.exceptions.base_exceptions import BaseException as InternalException


class WDGTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        self.user = User.objects.get(username=attrs[self.username_field])

        refresh = self.get_wdg_token(self.user, self.context.get("request"))

        data = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

        if api_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, self.user)

        return data

    @classmethod
    def get_token(cls, user):
        return super().get_token(user)

    @classmethod
    def get_wdg_token(cls, user, request):
        if not getattr(request, "tenant", None):
            raise InternalException("No tenant provided in request")

        token = cls.get_token(user)
        token["is_superuser"] = user.is_superuser
        token["domain_url"] = request.tenant.domain_url
        token["schema_name"] = request.tenant.schema_name

        return token


class WDGTokenRefreshSerializer(TokenRefreshSerializer):

    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])

        data = {"access": str(refresh.access_token)}

        if api_settings.ROTATE_REFRESH_TOKENS:
            if api_settings.BLACKLIST_AFTER_ROTATION:
                try:
                    # Attempt to blacklist the given refresh token
                    refresh.blacklist()
                except AttributeError:
                    # If blacklist app not installed, `blacklist` method will
                    # not be present
                    pass

            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()

            # Store new Refresh Token
            OutstandingToken.objects.create(
                user_id=refresh[api_settings.USER_ID_CLAIM],
                jti=refresh[api_settings.JTI_CLAIM],
                token=str(refresh),
                created_at=refresh.current_time,
                expires_at=datetime_from_epoch(refresh["exp"]),
            )

            data["refresh"] = str(refresh)

        return data
