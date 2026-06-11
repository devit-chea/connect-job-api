from django.core.management import call_command
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.base.mixins.custom_jwt_request_mixin import CustomJWTRequestMixin
from apps.base.mixins.permission_mixin import PermissionWithUserTypeMixin


class RebuildSearchIndexView(
    PermissionWithUserTypeMixin, CustomJWTRequestMixin, APIView
):
    allowed_user_types = ("super_admin",)

    def post(self, request, *args, **kwargs):
        call_command("search_index", "--rebuild", verbosity=0, force=True)
        return Response(
            {"detail": "Search index rebuilt successfully."}, status=status.HTTP_200_OK
        )
