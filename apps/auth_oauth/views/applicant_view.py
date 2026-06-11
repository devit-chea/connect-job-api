from rest_framework import status
from rest_framework.response import Response

from apps.auth_oauth.constants.auth_constants import UserTypes, UserStatus
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.serializers.applicant_serializer import (
    ApplicantSignupSerializer,
    ApplicantProfileSignupSerializer,
    ApplicantToRecruiterSerializer,
    JobPreferenceSerializer,
)
from apps.auth_oauth.services.user_company_profile_service import UserCompanyProfileService
from apps.auth_oauth.utils.altcha_util import verify_altcha_or_none
from apps.auth_oauth.utils.auth_util import get_active_profile_id
from apps.auth_oauth.utils.rate_limit import rate_limit
from apps.auth_totp_mail.utils import email
from apps.base.models.company_model import Company
from apps.base.views.base_views import BaseCreateAPIView, BaseRetrieveAPIView
from apps.core.exceptions.base_exceptions import BadRequestException


class ApplicantActivePreferenceView(BaseRetrieveAPIView):
    queryset = Profile.objects.all()
    serializer_class = JobPreferenceSerializer

    def retrieve(self, request, *args, **kwargs):
        active_profile_id, _ = get_active_profile_id(request)
        instance = Profile.objects.filter(id=active_profile_id).first()
        preference = instance.job_preference if instance else None
        serializer = self.get_serializer(preference)
        return Response(serializer.data)


class ApplicantPreferenceView(BaseCreateAPIView):
    queryset = Profile.objects.all()
    serializer_class = JobPreferenceSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        active_profile_id, _ = get_active_profile_id(request)
        Profile.objects.filter(id=active_profile_id).update(
            job_preference=validated_data
        )

        return Response(serializer.data, status=201)


class ApplicantToRecruiterSignupView(BaseCreateAPIView):
    """
    API for applicant to become recruiter
    """

    queryset = Company.objects.all()
    serializer_class = ApplicantToRecruiterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, profile_type=UserTypes.ADMIN_RECRUITER.value
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=201, headers=headers)


class ApplicantSignupView(BaseCreateAPIView):
    """
    API for applicant normal signup user
    """

    permission_classes = ()
    queryset = User.objects.all()
    serializer_class = ApplicantSignupSerializer

    def create(self, request, *args, **kwargs):
        altcha = request.data.get("altcha", "")
        ok, _ = verify_altcha_or_none(altcha)

        if not ok:
            return Response(
                {"detail": "Unable to create the account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        username = request.data.get("username")
        existing_user = User.objects.filter(
            email=username,
            status=UserStatus.ACTIVE,
            login_type="social",
            is_active=True,
        ).first()
        if existing_user:
            if UserCompanyProfileService.has_recruiter(existing_user.pk):
                raise BadRequestException(
                    "Unable to create the account."
                )
            existing_user.is_required_reset_pwd = True
            existing_user.save(update_fields=["is_required_reset_pwd"])
            return email.is_required_email_confirm_login(request, existing_user)

        serializer = self.get_serializer(
            data=request.data, profile_type=UserTypes.APPLICANT.value
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        return email.is_required_email_confirm_login(request, instance)


class ApplicantProfileSignupView(BaseCreateAPIView):
    """
    API for recruiter normal signup profile
    """

    queryset = Profile.objects.all()
    serializer_class = ApplicantProfileSignupSerializer
