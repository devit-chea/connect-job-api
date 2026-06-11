from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response

from apps.auth_oauth.constants.auth_constants import (
    UserTypes,
    ProfileStatus,
    UserStatus,
)
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.auth_oauth.serializers.profile_serializer import (
    RecruiterProfessionalDetailSerializer,
)
from apps.auth_oauth.serializers.recruiter_serializer import (
    RecruiterSignupSerializer,
    RecruiterProfileSignupSerializer,
    RecruiterCompanyProfileSerializer,
)
from apps.auth_oauth.services.user_company_profile_service import UserCompanyProfileService
from apps.auth_oauth.utils.altcha_util import verify_altcha_or_none
from apps.auth_oauth.utils.auth_util import get_active_profile_id
from apps.auth_oauth.utils.rate_limit import rate_limit
from apps.auth_totp_mail.utils import email
from apps.base.decorators.permission_decorator import permission
from apps.base.models.company_model import Company
from apps.base.views.base_views import (
    BaseRetrieveAPIView,
    BaseUpdateAPIView,
    BaseRetrieveUpdateAPIView,
)
from apps.core.exceptions.base_exceptions import BadRequestException


class RecruiterSignupView(CreateAPIView):
    """
    API for recruiter normal signup user
    """

    permission_classes = ()
    queryset = User.objects.all()
    serializer_class = RecruiterSignupSerializer

    def create(self, request, *args, **kwargs):
        altcha = request.data.get("altcha")
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
            if UserCompanyProfileService.has_applicant(existing_user.pk):
                raise BadRequestException(
                    "Unable to create the account."
                )
            existing_user.is_required_reset_pwd = True
            existing_user.save(update_fields=["is_required_reset_pwd"])
            return email.is_required_email_confirm_login(request, existing_user)

        serializer = self.get_serializer(
            data=request.data, profile_type=UserTypes.ADMIN_RECRUITER.value
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        return email.is_required_email_confirm_login(request, instance)


class RecruiterProfileCreateView(CreateAPIView):
    """
    API for recruiter normal signup profile
    """

    queryset = Profile.objects.all()
    serializer_class = RecruiterProfileSignupSerializer


class RecruiterCompanyProfileView(BaseRetrieveAPIView):
    queryset = Company.objects.all()
    serializer_class = RecruiterCompanyProfileSerializer

    def retrieve(self, request, *args, **kwargs):
        _, user_company_profile_id = get_active_profile_id(request)
        user_company_profile_instance = UserCompanyProfile.objects.filter(
            id=user_company_profile_id, status=ProfileStatus.ACTIVE
        ).last()
        instance = (
            user_company_profile_instance.company
            if user_company_profile_instance
            else None
        )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class RecruiterCompanyProfileUpdateView(BaseUpdateAPIView):
    queryset = Company.objects.all()
    serializer_class = RecruiterCompanyProfileSerializer

    def update(self, request, *args, **kwargs):
        _, user_company_profile_id = get_active_profile_id(request)
        user_company_profile_instance = UserCompanyProfile.objects.filter(
            id=user_company_profile_id, status=ProfileStatus.ACTIVE
        ).last()
        instance = (
            user_company_profile_instance.company
            if user_company_profile_instance
            else None
        )
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


class RecruiterProfessionalDetailUpdateView(BaseRetrieveUpdateAPIView):
    queryset = Profile.objects.all()
    serializer_class = RecruiterProfessionalDetailSerializer
    permission_codename = ["recruiter_manage_profile"]

    def get_object(self):
        active_profile_id, _ = get_active_profile_id(self.request)
        instance = Profile.objects.filter(id=active_profile_id).first()
        if not instance:
            raise BadRequestException("Profile not found.")
        return instance

    @permission(permission_codename=["recruiter_manage_profile"])
    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
