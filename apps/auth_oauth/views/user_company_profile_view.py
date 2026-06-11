# user profile
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.auth_oauth.serializers.user_company_profile_serializer import (
    UserCompanyProfileSerializer,
)
from rest_framework import generics
from rest_framework.response import Response


class UserCompanyProfileView(generics.ListAPIView):
    queryset = UserCompanyProfile.objects.all()
    serializer_class = UserCompanyProfileSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset().filter(user=request.user)
        queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
