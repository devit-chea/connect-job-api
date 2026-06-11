import logging
from django.conf import settings
from django.db import transaction
from django.db.models import Value, Q, Prefetch
from django.db.models.functions import Concat
from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
    OpenApiTypes,
)
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.core.exceptions.base_exceptions import BadRequestException

from apps.auth_oauth.constants.auth_constants import UserStatus, UserTypes, GroupTypes
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.models.role_model import Role
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.auth_oauth.serializers.admin_user_serializer import (
    AdminUserSerializer,
    OperatorAllRequestSerializer,
    OperatorApprovalSerializer,
    OperatorSendInviteSerializer,
    OperatorRequestDetailSerializer,
    RoleSerializer,
    OperatorRoleListSerializer,
)
from apps.auth_oauth.serializers.auth_serializer import CurrentUserSerializer
from apps.auth_oauth.services.send_email_service import EmailService
from apps.auth_oauth.services.user_role_service import UserRoleService
from apps.auth_oauth.utils.auth_util import get_user_agent_info
from apps.base.constants.base_constants import Status, CompanyStatusChoices
from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.services.company_service import CompanyService
from apps.base.views.base_views import (
    BaseModelViewSet,
    BaseListAPIView,
    BaseUpdateAPIView,
    BaseRetrieveAPIView,
)
from apps.auth_oauth.mixins.encryption_mixins import EncryptionMixin
from apps.auth_oauth.utils.redis_cache import (
    get_permission_cache_key,
    delete_cached_key,
)

encryption = EncryptionMixin()
logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                name="user_type",
                location=OpenApiParameter.QUERY,
                required=False,
                type=OpenApiTypes.STR,
                description="Filter by UserCompanyProfile.type (e.g. admin_recruiter, super_admin, recruiter,applicant)",
            )
        ]
    )
)
class OperatorUserView(PermissionMixin, BaseModelViewSet):
    """
    API for admin user management
    """

    USER_FIELDS = ["id", "is_active", "status", "username", "first_name", "last_name"]
    permission_codename = "operator_manage_user"
    queryset = User.objects.all().prefetch_related(
        Prefetch(
            "profile_user",
            queryset=Profile.objects.all(),
            to_attr="profiles_prefetched",
        )
    )
    serializer_class = AdminUserSerializer
    filterset_fields = USER_FIELDS
    search_fields = USER_FIELDS

    def get_queryset(self):
        # Start with the base queryset defined in the class attribute
        qs = (
            super()
            .get_queryset()
            .exclude(status=UserStatus.DELETED)
            .annotate(full_name=Concat("first_name", Value(" "), "last_name"))
            .order_by("-id")
        )

        ucp_type = self.request.query_params.get("user_type")

        if ucp_type == "created_by_me":
            user_id = getattr(self.request, "user_id", None)

            if user_id is not None:
                qs = qs.filter(create_uid=user_id)
            else:
                qs = qs.none()

        elif (
            ucp_type
        ):  # Only run this if a user_type other than "created_by_me" is provided
            if ucp_type not in GroupTypes.values:
                raise BadRequestException(
                    f"Invalid user_type: {ucp_type}. Must be one of {list(GroupTypes.values)} or 'created_by_me'."
                )
            user_ids = (
                UserCompanyProfile.objects.filter(type=ucp_type)
                .values_list("user_id", flat=True)
                .distinct()
            )
            qs = qs.filter(id__in=user_ids)

        return qs

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.status = UserStatus.DELETED
        instance.is_login = True
        instance.save()
        return Response(status=204)


class OperatorAllRequestView(PermissionMixin, BaseListAPIView):
    """
    API endpoint for Operators and Super Admins to view a list of all Profile
    requests (e.g., pending profile submissions, company registrations).
    """

    serializer_class = OperatorAllRequestSerializer
    permission_codename = "operator_all_request"
    filterset_fields = [
        "first_name",
        "last_name",
        "profile_type",
        "status",
        "submitted_date",
        "company__name",
    ]
    search_fields = [
        "first_name",
        "last_name",
        "profile_type",
        "status",
        "submitted_date",
        "company__name",
    ]

    def get_queryset(self):
        queryset = Profile.objects.all()
        filtered_queryset = queryset.filter(
            Q(company__isnull=False)
            & ~Q(company__status=CompanyStatusChoices.DRAFT.value)
            & ~Q(profile_type=UserTypes.APPLICANT.value)
        )

        return filtered_queryset


class OperatorApprovalView(PermissionMixin, BaseUpdateAPIView):
    queryset = Profile.objects.exclude(profile_type=UserTypes.APPLICANT.value)
    serializer_class = OperatorApprovalSerializer
    permission_codename = "operator_manage_request_approval"
    
    @transaction.atomic()
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        status = validated_data.get("status", None)
        instance.status = status
        instance.approval_reason = validated_data.get("approval_reason", None)
        instance.save()
        
        # Update the Company status to Approved
        company_id = instance.company_id
        # NOTE : maybe change later
        CompanyService(context={"request": request}).update_approved_company(
            company_id, status
        )
        
        # Approved turn it to full role-permission
        user_company_profile = UserCompanyProfile.objects.filter(profile_id=instance.id)
        if status == Status.APPROVED:
            for ucp in user_company_profile:
                UserRoleService.promote_pending_admin_to_full(ucp)

                # Clear Old Permission Cache After Approved
                try:
                    if getattr(settings, "AUTH_PERMISSION_CACHE_ENABLED", False):
                        cache_key = get_permission_cache_key(
                            user_id=ucp.user.id, user_company_profile_id=ucp.id
                        )
                        if cache_key:
                            delete_cached_key(cache_key)
                except Exception as e:
                    logger.error(f"Error Clear Permission Cache: {e}")
        
        return Response(serializer.data)


class OperatorSendInviteView(BaseUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = OperatorSendInviteSerializer

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            default_password = encryption.decrypt_value(instance.default_password)
            template_context = EmailService().template_context(
                user=instance, default_password=default_password
            )
            EmailService().send_invite(instance, template_context)
        except Exception as e:
            raise e

        return Response("ok")


class OperatorCurrentUserView(APIView):

    def get(self, request):
        if request.user.is_anonymous:
            return Response({"is_anonymous": True})
        user_agent = get_user_agent_info(request.user, request)
        serializer = CurrentUserSerializer(
            request.user, context={"request": request, "user_agent": user_agent}
        )
        return Response(serializer.data)


class OperatorRequestDetailView(PermissionMixin, BaseRetrieveAPIView):
    queryset = Profile.objects.all()
    serializer_class = OperatorRequestDetailSerializer
    permission_codename = "operator_all_request"


class OperatorRolesView(PermissionMixin, BaseModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_codename = "operator_manage_role"
    search_fields = ["id", "name", "code", "description"]


class OperatorRoleListView(PermissionMixin, BaseListAPIView):
    search_fields = ["id", "name", "code", "description"]
    queryset = Role.objects.all()
    serializer_class = OperatorRoleListSerializer
    permission_codename = "operator_manage_role"
    
    def list(self, request, *args, **kwargs):
        company = kwargs.get("company", None)
        _type = kwargs.get("type", None)
        queryset = Role.objects.filter(company=company, type=_type)
        queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

