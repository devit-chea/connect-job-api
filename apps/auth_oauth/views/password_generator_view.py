from rest_framework.decorators import api_view,permission_classes
from rest_framework.response import Response
from apps.base.utils.base_util import password_generator
from rest_framework.permissions import IsAuthenticated, AllowAny


@api_view(["GET"])
@permission_classes([AllowAny])
def password_generator_api(request):
    """
    API for generate random password 8 characters
    """
    password = password_generator(length=8)

    return Response({"password": password})
