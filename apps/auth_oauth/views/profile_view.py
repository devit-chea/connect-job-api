from typing import Dict, Set
from uuid import UUID

from django.db.models import F
from django.db.models.functions.comparison import Coalesce
from django.db.models.functions.text import Lower
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auth_oauth.models.education_model import Education
from apps.auth_oauth.models.portfolio_model import Portfolio
from apps.auth_oauth.models.profile_language_model import ProfileLanguage
from apps.auth_oauth.models.profile_model import Profile, ProfileDocumentModel
from apps.auth_oauth.models.reference_model import Reference
from apps.auth_oauth.models.skill_model import Skill
from apps.auth_oauth.models.work_experience_model import WorkExperience
from apps.auth_oauth.serializers.education_serializer import EducationsProfileSerializer
from apps.auth_oauth.serializers.languages_serializer import LanguagesProfileSerializer
from apps.auth_oauth.serializers.portfolio_serializer import PortfoliosProfileSerializer
from apps.auth_oauth.serializers.profile_document_serializer import (
    ProfileDocumentSerializer,
)
from apps.auth_oauth.serializers.profile_serializer import (
    ProfileApplicantUpdateSerializer,
    ApplicantProfileRetrieveSerializer,
    ProfileImagesUpdateSerializer,
)
from apps.auth_oauth.serializers.reference_serializer import ReferencesProfileSerializer
from apps.auth_oauth.serializers.skill_serializer import SkillsProfileSerializer
from apps.auth_oauth.serializers.work_experience_serializer import (
    WorkExperiencesProfileSerializer,
)
from apps.auth_oauth.services.user_profile_service import UserProfileService
from apps.auth_oauth.utils.auth_util import get_active_profile_id
from apps.auth_oauth.utils.profile_queryset import profile_completion_annotations
from apps.auth_oauth.utils.utils import group_work_experiences, group_educations
from apps.base.decorators.permission_decorator import permission
from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.utils.file_management_util import FileURLService
from apps.base.views.base_views import (
    BaseUpdateAPIView,
    BaseRetrieveAPIView,
    BaseListAPIView,
    BaseModelViewSet,
)
from apps.core.exceptions.base_exceptions import BadRequestException

CATEGORIES = ("cv", "cover_letter", "additional", "certificate", "other", "portfolio")


class ApplicantProfileUpdateView(BaseUpdateAPIView):
    """
    API for applicant update profile.
    """

    queryset = Profile.objects.all()
    serializer_class = ProfileApplicantUpdateSerializer

    def get_object(self):
        active_profile_id, _ = get_active_profile_id(self.request)
        instance = Profile.objects.filter(id=active_profile_id).first()
        if not instance:
            raise BadRequestException("Profile not found.")
        return instance

    def get_serializer_class(self):
        if self.request and self.request.method.upper() == "PATCH":
            return ProfileImagesUpdateSerializer
        return ProfileApplicantUpdateSerializer

    @permission(
        permission_codename=[
            "recruiter_manage_profile",
            "applicant_manage_profile",
            "admin_recruiter_manage_profile",
        ]
    )
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    @permission(
        permission_codename=[
            "recruiter_manage_profile",
            "applicant_manage_profile",
            "admin_recruiter_manage_profile",
        ]
    )
    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


class ApplicantActiveProfileRetrieveView(BaseRetrieveAPIView):
    queryset = profile_completion_annotations(Profile.objects.all())
    serializer_class = ApplicantProfileRetrieveSerializer

    @permission(
        permission_codename=[
            "recruiter_manage_profile",
            "applicant_manage_profile",
            "admin_recruiter_manage_profile",
        ]
    )
    def retrieve(self, request, *args, **kwargs):
        active_profile_id, _ = get_active_profile_id(request)
        instance = self.get_queryset().filter(id=active_profile_id).first()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class WorkExperiencesActiveProfileView(BaseListAPIView):
    queryset = WorkExperience.objects.all()
    serializer_class = WorkExperiencesProfileSerializer

    @permission(permission_codename="applicant_manage_profile")
    def list(self, request, *args, **kwargs):
        active_profile_id, _ = get_active_profile_id(request)
        queryset = (
            WorkExperience.objects.filter(user_profile_id=active_profile_id)
            .select_related("company", "location")
            .annotate(
                company_display=Coalesce("company__name", "company_name"),
                company_key_lower=Lower(Coalesce("company__name", "company_name")),
            )
            .order_by(
                F("is_currently_work").desc(),
                F("start_date").desc(),
                F("end_date").desc(nulls_last=True),
            )
        )
        queryset = self.filter_queryset(queryset)
        data = self.get_serializer(queryset, many=True).data
        grouped_work_experiences = group_work_experiences(data)
        return Response(grouped_work_experiences)


class EducationsActiveProfileView(BaseListAPIView):
    queryset = Education.objects.all()
    serializer_class = EducationsProfileSerializer

    @permission(permission_codename="applicant_manage_profile")
    def list(self, request, *args, **kwargs):
        active_profile_id, _ = get_active_profile_id(request)
        queryset = Education.objects.filter(user_profile_id=active_profile_id)
        queryset = self.filter_queryset(queryset)
        data = self.get_serializer(queryset, many=True).data
        grouped_educations = group_educations(data)
        return Response(grouped_educations)


class SkillsActiveProfileView(BaseListAPIView):
    queryset = Skill.objects.all()
    serializer_class = SkillsProfileSerializer

    @permission(permission_codename="applicant_manage_profile")
    def list(self, request, *args, **kwargs):
        active_profile_id, _ = get_active_profile_id(request)
        queryset = Skill.objects.filter(user_profile_id=active_profile_id)
        queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ReferencesActiveProfileView(BaseListAPIView):
    queryset = Reference.objects.all()
    serializer_class = ReferencesProfileSerializer

    @permission(permission_codename="applicant_manage_profile")
    def list(self, request, *args, **kwargs):
        active_profile_id, _ = get_active_profile_id(request)
        queryset = Reference.objects.filter(user_profile_id=active_profile_id)
        queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class PortfoliosActiveProfileView(BaseListAPIView):
    queryset = Portfolio.objects.all()
    serializer_class = PortfoliosProfileSerializer

    @permission(permission_codename="applicant_manage_profile")
    def list(self, request, *args, **kwargs):
        active_profile_id, _ = get_active_profile_id(request)
        queryset = Portfolio.objects.filter(user_profile_id=active_profile_id)
        queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class LanguagesProfileActiveProfileView(BaseListAPIView):
    queryset = ProfileLanguage.objects.all()
    serializer_class = LanguagesProfileSerializer

    @permission(permission_codename="applicant_manage_profile")
    def list(self, request, *args, **kwargs):
        active_profile_id, _ = get_active_profile_id(request)
        queryset = ProfileLanguage.objects.filter(user_profile_id=active_profile_id)
        queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ManageApplicantProfilePermission(PermissionMixin):
    """
    Mange all permission class under profile
    """

    permission_codename = "applicant_manage_profile"


class WorkExperiencesProfileView(ManageApplicantProfilePermission, BaseModelViewSet):
    queryset = WorkExperience.objects.all()
    serializer_class = WorkExperiencesProfileSerializer


class EducationsProfileView(ManageApplicantProfilePermission, BaseModelViewSet):
    queryset = Education.objects.all()
    serializer_class = EducationsProfileSerializer


class SkillsProfileView(ManageApplicantProfilePermission, BaseModelViewSet):
    queryset = Skill.objects.all()
    serializer_class = SkillsProfileSerializer


class ReferencesProfileView(ManageApplicantProfilePermission, BaseModelViewSet):
    queryset = Reference.objects.all()
    serializer_class = ReferencesProfileSerializer


class PortfoliosProfileView(ManageApplicantProfilePermission, BaseModelViewSet):
    queryset = Portfolio.objects.all()
    serializer_class = PortfoliosProfileSerializer


class LanguagesProfileView(ManageApplicantProfilePermission, BaseModelViewSet):
    queryset = ProfileLanguage.objects.all()
    serializer_class = LanguagesProfileSerializer


class ProfileDocumentView(BaseModelViewSet):
    """
    Endpoint to manage profile documents
    """

    queryset = ProfileDocumentModel.objects.all()
    serializer_class = ProfileDocumentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = []
    pagination_class = None

    def get_queryset(self):
        request = self.request
        profile_id, _ = get_active_profile_id(request)
        if not profile_id:
            return ProfileDocumentModel.objects.none()
        return ProfileDocumentModel.objects.filter(profile_id=profile_id)

    def list(self, request, *args, **kwargs):
        profile_id, user_company_profile_id = get_active_profile_id(request)
        if not profile_id:
            return Response(
                {"detail": "profile_id not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        file_ids_by_category: Dict[str, list[tuple[int, UUID]]] = {
            c: [] for c in CATEGORIES
        }

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
                    "file_id": file_id,
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


class RecruiterListApplicantWorkExperiencesView(BaseListAPIView):
    queryset = WorkExperience.objects.all()
    serializer_class = WorkExperiencesProfileSerializer

    @permission(
        permission_codename=["recruiter_applicant", "admin_recruiter_applicant"]
    )
    def list(self, request, *args, **kwargs):
        profile_id = kwargs.get("profile_id")
        queryset = (
            WorkExperience.objects.filter(user_profile_id=profile_id)
            .select_related("company", "location")
            .annotate(
                company_display=Coalesce("company__name", "company_name"),
                company_key_lower=Lower(Coalesce("company__name", "company_name")),
            )
        )
        queryset = self.filter_queryset(queryset)
        data = self.get_serializer(queryset, many=True).data
        grouped_work_experiences = group_work_experiences(data)
        return Response(grouped_work_experiences)


class RecruiterListApplicantEducationsView(BaseListAPIView):
    queryset = Education.objects.all()
    serializer_class = EducationsProfileSerializer

    @permission(
        permission_codename=["recruiter_applicant", "admin_recruiter_applicant"]
    )
    def list(self, request, *args, **kwargs):
        profile_id = kwargs.get("profile_id")
        queryset = Education.objects.filter(user_profile_id=profile_id)
        queryset = self.filter_queryset(queryset)
        data = self.get_serializer(queryset, many=True).data
        grouped_educations = group_educations(data)
        return Response(grouped_educations)


class RecruiterListApplicantSkillsView(BaseListAPIView):
    queryset = Skill.objects.all()
    serializer_class = SkillsProfileSerializer

    @permission(
        permission_codename=["recruiter_applicant", "admin_recruiter_applicant"]
    )
    def list(self, request, *args, **kwargs):
        profile_id = kwargs.get("profile_id")
        queryset = Skill.objects.filter(user_profile_id=profile_id)
        queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class RecruiterListApplicantLanguagesView(BaseListAPIView):
    queryset = ProfileLanguage.objects.all()
    serializer_class = LanguagesProfileSerializer

    @permission(
        permission_codename=["recruiter_applicant", "admin_recruiter_applicant"]
    )
    def list(self, request, *args, **kwargs):
        profile_id = kwargs.get("profile_id")
        queryset = ProfileLanguage.objects.filter(user_profile_id=profile_id)
        queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class MyProfileDocumentByTypeView(BaseRetrieveAPIView):
    """
    Endpoint to get profile documents by type.
    """

    queryset = ProfileDocumentModel.objects.all()
    serializer_class = ProfileDocumentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "document_type"

    def get_queryset(self):
        request = self.request
        profile_id, _ = get_active_profile_id(request)
        if not profile_id:
            return ProfileDocumentModel.objects.none()
        return ProfileDocumentModel.objects.filter(
            profile_id=profile_id, status="ACTIVE"
        )

    @permission(permission_codename="applicant_manage_profile")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
