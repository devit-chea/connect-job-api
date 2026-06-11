import logging
from typing import Dict, Set
from uuid import UUID

from django.db import transaction
from django.db.models.functions.comparison import Coalesce
from django.db.models.functions.text import Lower
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError

from apps.auth_oauth.constants.jwt_constants import TokenTypeHeader
from apps.auth_oauth.models.education_model import Education
from apps.auth_oauth.models.link_model import Link
from apps.auth_oauth.models.profile_language_model import ProfileLanguage
from apps.auth_oauth.models.profile_model import Profile, ProfileDocumentModel
from apps.auth_oauth.models.skill_model import Skill
from apps.auth_oauth.models.work_experience_model import WorkExperience
from apps.auth_oauth.serializers.auth_serializer import (
    LoginSerializer,
    RefreshTokenSerializer,
)
from apps.auth_oauth.serializers.mobile_serializer import (
    MobileCurrentProfileSerializer,
    MobileEducationSerializer,
    MobileWorkExperienceSerializer,
    MobileProfileLanguageSerializer,
    MobileSkillSerializer,
    MobileUpdateCurrentProfileSerializer,
    MobileLinkSerializer, MobileProfileDocumentSerializer,
)
from apps.auth_oauth.services.user_profile_service import UserProfileService
from apps.auth_oauth.utils.auth_util import get_active_profile_id
from apps.auth_oauth.utils.utils import group_educations, group_work_experiences
from apps.auth_oauth.views.views import LoginView
from apps.base.utils.custom_filter import ApplicantOwnerScopeFilterBackend
from apps.base.utils.file_management_util import FileURLService
from apps.base.views.base_views import (
    BaseUpdateAPIView,
    BaseModelViewSet,
)
from apps.core.exceptions.base_exceptions import BadRequestException


logger = logging.getLogger(__name__)

CATEGORIES = ("cv", "cover_letter", "additional", "certificate", "other", "portfolio")


class MobileLoginView(LoginView):
    permission_classes = ()
    serializer_class = LoginSerializer
    http_method_names = ["post"]

    def post(self, request: Request, *args, **kwargs):
        request.META["HTTP_TOKEN_TYPE"] = TokenTypeHeader.jwt
        return super().post(request, *args, **kwargs)


class MobileRefreshTokenView(CreateAPIView):
    serializer_class = RefreshTokenSerializer
    permission_classes = ()

    def create(self, request, *args, **kwargs):
        try:
            request.data.update({"client": "mobile"})
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            response = Response(serializer.data, status=status.HTTP_200_OK)
            return response
        except TokenError as e:
            response = Response(
                {"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
            )

        return response


class MobileUpdateActiveProfileView(BaseUpdateAPIView):
    queryset = Profile.objects.all()
    serializer_class = MobileUpdateCurrentProfileSerializer

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        active_profile_id, _ = get_active_profile_id(request)
        instance = Profile.objects.filter(id=active_profile_id).first()
        if not instance:
            raise BadRequestException("Profile not found.")
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


class MobileActiveProfileView(RetrieveAPIView):
    queryset = Profile.objects.all()
    serializer_class = MobileCurrentProfileSerializer

    def retrieve(self, request, *args, **kwargs):
        try:
            active_profile_id, _ = get_active_profile_id(request)
            active_profile = Profile.objects.filter(id=active_profile_id).first()
            
            if not active_profile:
                raise BadRequestException("Profile not found.")
            
            serializer = self.get_serializer(active_profile)
            return Response(serializer.data)

        except BadRequestException as e:
            logger.error(f"Error: {e}")
            raise e
            
        except Exception as e:
            # Catch unexpected errors (DB connection, attribute errors, etc.)
            logger.error(f"Profile error: {e}")
            return Response(
                {"detail": "An unexpected error occurred while retrieving the profile."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ApplicantOwnerScopedViewSet(BaseModelViewSet):
    filter_backends = BaseModelViewSet.filter_backends + [
        ApplicantOwnerScopeFilterBackend
    ]


class MobileEducationView(ApplicantOwnerScopedViewSet):
    queryset = Education.objects.all()
    serializer_class = MobileEducationSerializer

    def list(self, request, *args, **kwargs):
        active_profile_id, _ = get_active_profile_id(request)
        queryset = Education.objects.filter(user_profile_id=active_profile_id)
        data = self.get_serializer(queryset, many=True).data
        grouped_educations = group_educations(data)
        return Response(grouped_educations)


class MobileWorkExperienceView(ApplicantOwnerScopedViewSet):
    queryset = WorkExperience.objects.all()
    serializer_class = MobileWorkExperienceSerializer

    def list(self, request, *args, **kwargs):
        active_profile_id, _ = get_active_profile_id(request)
        queryset = (WorkExperience.objects.filter(user_profile_id=active_profile_id)
        .select_related("company", "location").annotate(
            company_display=Coalesce("company__name", "company_name"),
            company_key_lower=Lower(Coalesce("company__name", "company_name")),
        ))
        data = self.get_serializer(queryset, many=True).data
        grouped_work_experiences = group_work_experiences(data)
        return Response(grouped_work_experiences)


class MobileSkillView(ApplicantOwnerScopedViewSet):
    queryset = Skill.objects.all()
    serializer_class = MobileSkillSerializer

    def list(self, request, *args, **kwargs):
        active_profile_id, _ = get_active_profile_id(request)
        queryset = Skill.objects.filter(user_profile_id=active_profile_id)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class MobileLanguageView(ApplicantOwnerScopedViewSet):
    queryset = ProfileLanguage.objects.all()
    serializer_class = MobileProfileLanguageSerializer

    def list(self, request, *args, **kwargs):
        active_profile_id, _ = get_active_profile_id(request)
        queryset = ProfileLanguage.objects.filter(user_profile_id=active_profile_id)
        data = self.filter_queryset(queryset)
        page = self.paginate_queryset(data)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class MobileLinkView(ApplicantOwnerScopedViewSet):
    queryset = Link.objects.all()
    serializer_class = MobileLinkSerializer

    def list(self, request, *args, **kwargs):
        active_profile_id, _ = get_active_profile_id(request)
        queryset = Link.objects.filter(user_profile_id=active_profile_id)
        data = self.filter_queryset(queryset)
        page = self.paginate_queryset(data)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class MobileProfileDocumentView(BaseModelViewSet):
    """
    Endpoint to manage profile documents
    """
    filter_backends = []
    pagination_class = None
    queryset = ProfileDocumentModel.objects.all()
    serializer_class = MobileProfileDocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        request = self.request
        profile_id, _ = get_active_profile_id(request)
        if not profile_id:
            return ProfileDocumentModel.objects.none()
        return (
            ProfileDocumentModel.objects
            .filter(profile_id=profile_id)
        )

    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        """
        Mark this document as default for the profile
        """

        document = self.get_object()
        ProfileDocumentModel.set_as_default(document.profile, document.id, document.document_type)

        return Response({"detail": "Document set as default successfully."}, status=status.HTTP_200_OK)


    def list(self, request, *args, **kwargs):
        profile_id, user_company_profile_id = get_active_profile_id(request)
        if not profile_id:
            return Response(
                {"detail": "profile_id not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        file_ids_by_category: Dict[str, list[tuple[int, UUID]]] = {c: [] for c in CATEGORIES}

        profile_docs_qs = ProfileDocumentModel.objects.filter(
            profile_id=profile_id,
            status=ProfileDocumentModel.Status.ACTIVE,
        ).values("id", "document_id", "document_type")
        for row in profile_docs_qs:
            file_id = UserProfileService().to_uuid(row.get("document_id"))
            if file_id is None:
                continue
            category = row.get("document_type")
            file_ids_by_category[category].append((row.get("id"), file_id))

        all_file_ids: Set[UUID] = set()
        for category_name in CATEGORIES:
            fids = [fid for _, fid in file_ids_by_category[category_name]]
            all_file_ids.update(fids)
        file_metadata_by_file_id = FileURLService.map_by_file_ids(all_file_ids)
        documents = {
            category_name: [
                {
                    "id": doc_id,
                    "file_path": file_metadata["file_path"],
                    "file_type": file_metadata["file_type"],
                    "file_name": file_metadata["file_name"],
                    "file_size": file_metadata["file_size"],
                    "original_file_name": file_metadata["original_file_name"],
                }
                for doc_id, file_id in file_ids_by_category[category_name]
                if (file_metadata := file_metadata_by_file_id.get(file_id)) is not None
            ]
            for category_name in CATEGORIES
        }
        return Response({"documents": documents})

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
