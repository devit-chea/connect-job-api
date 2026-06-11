import datetime

from altcha import ChallengeOptions, create_challenge
from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.auth_oauth.serializers.altcha_serializer import AltchaChallengeSerializer


class AltchaChallengeAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        options = ChallengeOptions(
            expires=datetime.datetime.now()
            + datetime.timedelta(seconds=settings.ALTCHA_EXPIRY),
            max_number=getattr(settings, "ALTCHA_DESIRED_MAX_NUMBER"),
            hmac_key=getattr(settings, "ALTCHA_HMAC_KEY", ""),
        )
        challenge = create_challenge(options)

        serializer = AltchaChallengeSerializer(challenge)

        return Response(serializer.data)
