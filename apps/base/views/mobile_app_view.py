from django.conf import settings
from rest_framework import generics
from packaging.version import Version
from rest_framework.views import APIView
from rest_framework.response import Response
from django.http import HttpResponseRedirect

from apps.base.serializers.mobile_app_serializer import CheckForceUpdateSerializer


class CheckForceUpdateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        serializer = CheckForceUpdateSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        app_version = serializer.validated_data["app_version"]
        platform = serializer.validated_data["platform"]

        min_version = (
            settings.IOS_MIN_VERSION
            if platform == "ios"
            else settings.ANDROID_MIN_VERSION
        )

        need_force_update = Version(app_version) < Version(min_version)

        return Response(
            {
                "needForceUpdate": need_force_update,
                "appStoreUrl": settings.APP_STORE_URL,
                "playStoreUrl": settings.PLAY_STORE_URL,
            }
        )


class PublicMobileAppLinkView(generics.ListAPIView):
    throttle_classes = ()
    permission_classes = []
    authentication_classes = []

    @staticmethod
    def _mobile_link_view(request):
        mobile_play_store = settings.PLAY_STORE_URL
        app_store_store = settings.APP_STORE_URL

        if request.user_agent.os.family.lower() in ["ios", "macos", "ipados", "mascos"]:
            return HttpResponseRedirect(app_store_store)
        else:
            return HttpResponseRedirect(mobile_play_store)

    def list(self, request, *args, **kwargs):
        return self._mobile_link_view(request=request)
