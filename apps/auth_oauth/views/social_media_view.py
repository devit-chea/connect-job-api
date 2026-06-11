import logging
from django.shortcuts import redirect
from rest_framework.generics import RetrieveAPIView, CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.auth_oauth.constants.provider_constants import ProviderConstants
from apps.auth_oauth.serializers.social_serializer import (
    MobileGoogleSerializer,
    MobileLinkedInSerializer,
    GoogleCallbackSerializer,
    LinkedinCallbackSerializer,
    UserAuthenticationRedirectUrlSerializer, MobileAppleSerializer

)
from apps.auth_oauth.services.auth_service import SocialAuthService
from apps.auth_oauth.services.social_media_service import SocialMediaService
from apps.auth_oauth.utils.auth_util import redirect_to_frontend
from apps.core.exceptions.base_exceptions import BadRequestException
from config.settings import base as settings

logger = logging.getLogger(__name__)


class MobileLinkedInIntegrationView(CreateAPIView):
    permission_classes = [AllowAny]
    authentication_classes = ()
    serializer_class = MobileLinkedInSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        request.data["provider"] = ProviderConstants.LINKEDIN
        data, status_code = SocialAuthService().authenticate(request, *args, **kwargs)
        return Response(data, status=status_code)

class MobileAppleIntegrationView(CreateAPIView):
    permission_classes = [AllowAny]
    authentication_classes = ()
    serializer_class = MobileAppleSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        request.data["provider"] = ProviderConstants.APPLE
        data, status_code = SocialAuthService().authenticate(request, *args, **kwargs)
        return Response(data, status=status_code)

class GoogleCallbackView(RetrieveAPIView):
    permission_classes = ()
    authentication_classes = ()
    serializer_class = GoogleCallbackSerializer

    def get(self, request, *args, **kwargs):
        request.data["code"] = request.query_params.get("code", None)
        request.data["state"] = request.query_params.get("state", None)
        request.data["provider"] = ProviderConstants.GOOGLE
        try:
            # Validate the user has been created or not
            # if not created then create user
            # else just login
            response = SocialMediaService().sign_up_or_login(request, *args, **kwargs)
        except BadRequestException as e:
            logger.error(f"Google authentication failed: {e}")
            redirect_login_url = settings.WEB_BASE_URL_LOGIN
            return redirect(f"{redirect_login_url}")
        except Exception as e:
            logger.error(f"Google in failed to authentication {e.args}")
            redirect_login_url = settings.WEB_BASE_URL_LOGIN
            return redirect(f"{redirect_login_url}")  # to login page
        response = redirect_to_frontend(request, response)
        return response


class LinkedinCallbackView(RetrieveAPIView):
    permission_classes = ()
    authentication_classes = ()
    serializer_class = LinkedinCallbackSerializer

    def get(self, request, *args, **kwargs):
        request.data["code"] = request.query_params.get("code", None)
        request.data["state"] = request.query_params.get("state", None)
        request.data["provider"] = ProviderConstants.LINKEDIN
        try:
            response = SocialMediaService().sign_up_or_login(request, *args, **kwargs)
        except BadRequestException as e:
            logger.error(f"Linkedin authentication failed: {e}")
            redirect_login_url = settings.WEB_BASE_URL_LOGIN
            return redirect(f"{redirect_login_url}")
        except Exception as e:
            logger.error(f"Linked in failed to authentication {e}")
            redirect_login_url = settings.WEB_BASE_URL_LOGIN
            return redirect(f"{redirect_login_url}")  # to login page
        response = redirect_to_frontend(request, response)
        return response


class UserAuthenticationRedirectUrlView(CreateAPIView):
    permission_classes = ()
    authentication_classes = ()
    serializer_class = UserAuthenticationRedirectUrlSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return redirect(SocialMediaService().get_provider_auth_url(request.data.get("provider_name")))


class MobileGoogleIntegrationView(CreateAPIView):
    """
        Authentication with Linkedin
        Step 2: Accept token code from client to get access to
    """
    permission_classes = [AllowAny]
    authentication_classes = ()
    serializer_class = MobileGoogleSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        request.data["provider"] = ProviderConstants.GOOGLE
        data, status_code = SocialAuthService().authenticate(request, *args, **kwargs)
        return Response(data, status=status_code)


class LinkedinMobileCallbackView(RetrieveAPIView):
    """
        Accept Linkedin Callback
        Step 1: Accept notify from Linkedin
    """
    permission_classes = ()
    authentication_classes = ()
    serializer_class = LinkedinCallbackSerializer

    def get(self, request, *args, **kwargs):
        # nothing here 
        return Response("ok")
