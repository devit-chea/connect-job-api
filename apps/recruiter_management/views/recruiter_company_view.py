from django.db import transaction
from django.db.models.aggregates import Count
from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response

from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.models.company_model import Company
from apps.base.serializers.company_serializer import (
    CompanyRequestWithAdminRecruiterSerializer,
    RecruiterCompaniesListSerializer,
)
from apps.base.serializers.company_serializer import (
    CompanySerializer,
)
from apps.base.utils.base64image_util import Base64ImageUtil
from apps.base.views.base_views import (
    BaseModelViewSet,
    BaseCreateAPIView,
    BaseRetrieveAPIView,
)
from apps.base.views.base_views import BaseUpdateAPIView
from apps.core.exceptions.base_exceptions import BadRequestException
from apps.recruiter_management.serializers.recruiter_company_serializer import (
    CompanyResubmitSerializer,
    CompanyProfileImagesUpdateSerializer,
)


class RecruiterCompanyView(PermissionMixin, BaseModelViewSet):
    queryset = Company.objects.all()
    permission_codename = ["admin_recruiter_company", "recruiter_company"]
    search_fields = ["name", "code", "description", "email"]
    ordering_fields = ["name", "create_date", "write_date"]
    serializer_class = CompanySerializer

    def get_queryset(self):
        company_id = getattr(self.request, "company_id", None)
        user_id = getattr(self.request, "user_id", None)
        if not company_id:
            ucp_id = getattr(self.request, "user_company_profile_id", None)
            if ucp_id:
                company_id = (
                    UserCompanyProfile.objects.filter(id=ucp_id)
                    .values_list("company_id", flat=True)
                    .first()
                )

        if not (company_id or user_id):
            return Company.objects.none()

        cond = Q(id=company_id) | (Q(create_uid=user_id))
        current_date = timezone.now().date()
        return (
            super()
            .get_queryset()
            .filter(cond)
            .exclude(status="rejected")
            .annotate(
                job_count=Count(
                    "jobpostmodel",
                    filter=Q(jobpostmodel__status="ACTIVE")
                    & Q(jobpostmodel__expire_date__gte=current_date),
                )
            )
        )

    def get_object(self):
        qs = self.get_queryset()
        obj = get_object_or_404(qs, pk=self.kwargs.get("pk"))
        return obj

    def get_serializer_class(self):
        if self.action == "list":
            return RecruiterCompaniesListSerializer
        if self.action == "create":
            return CompanyRequestWithAdminRecruiterSerializer
        return CompanySerializer

    @transaction.atomic()
    def update(self, request, *args, **kwargs):
        validated_file = None
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        if "logo" in validated_data:
            validated_file = validated_data.get("logo")
        request_file = request.data.get("logo")
        ref_id = instance.pk
        ref_type = "company_logo"
        if validated_file:
            Base64ImageUtil.update_base64image(
                validated_file, request_file, ref_id, ref_type
            )
        serializer.save()
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class CompanyRequestInformationView(RetrieveAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer

    def retrieve(self, request, *args, **kwargs):
        ucp_id = request.auth.payload.get("user_company_profile_id", None)
        user = request.user
        if ucp_id is None:
            raise serializers.ValidationError({"detail": "No active profile."})
        ucp = (
            UserCompanyProfile.objects.select_related("company", "profile")
            .filter(id=ucp_id)
            .first()
        )
        rejected_count = Profile.objects.filter(user=user, status="rejected").count()
        MAX_REJECT = 3
        if not ucp or not ucp.company:
            raise serializers.ValidationError({"detail": "No active profile."})
        company = ucp.company
        data = self.get_serializer(company).data
        data["remaining_count"] = MAX_REJECT - rejected_count
        return Response(data)


class CompanyResubmitView(BaseCreateAPIView):
    serializer_class = CompanyResubmitSerializer
    permission_codename = ["admin_recruiter_company", "recruiter_company"]

    def get_serializer_context(self):
        return {"request": self.request}


class CompanyProfileRejectReasonView(BaseRetrieveAPIView):
    permission_codename = ["admin_recruiter_company", "recruiter_company"]

    def get(self, request, *args, **kwargs):
        ucp_id = request.auth.payload.get("user_company_profile_id")
        if not ucp_id:
            raise serializers.ValidationError({"detail": "No active profile."})
        ucp = (
            UserCompanyProfile.objects.select_related("profile")
            .filter(id=ucp_id)
            .first()
        )
        if not ucp or not ucp.profile:
            return Response({"reject_reason": None}, status=200)
        profile = ucp.profile
        if profile.status != "rejected":
            return Response({"reject_reason": None}, status=200)
        return Response(
            {
                "profile_id": profile.id,
                "status": profile.status,
                "reject_reason": profile.approval_reason,
            }
        )


class RecruiterUpdateProfileCompanyView(PermissionMixin, BaseUpdateAPIView):
    queryset = Company.objects.all()
    permission_codename = ["admin_recruiter_company", "recruiter_company"]
    serializer_class = CompanyProfileImagesUpdateSerializer

    def get_object(self):
        company_id = self.request.auth.payload.get("company_id", None)
        instance = Company.objects.filter(id=company_id).first()
        if not instance:
            raise BadRequestException("Company not found.")
        return instance

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
