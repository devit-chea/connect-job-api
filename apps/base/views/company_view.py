from django.conf import settings
from django.db.models import OuterRef, Subquery, CharField
from django.db.models.aggregates import Count
from django.db.models.functions import Cast
from django.db.models.query_utils import Q
from django.utils import timezone
from django_elasticsearch_dsl_drf.filter_backends import (
    DefaultOrderingFilterBackend,
    FilteringFilterBackend,
)
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import generics, status as http_status
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from apps.base.constants.base_constants import RefType, Status
from apps.base.mixins.custom_jwt_request_mixin import CustomJWTRequestMixin
from apps.base.models.company_model import Company
from apps.base.models.file_model import FileModel
from apps.base.serializers.company_serializer import (
    CompanySerializer,
    CompaniesListSerializer,
    CompanyIntegrationTabSerializer,
)
from apps.base.views.base_document_view_set import BasePublicDocumentViewSet
from apps.base.views.base_views import BaseListAPIView
from apps.core.exceptions.base_exceptions import BadRequestException, NotFoundException
from apps.core.pagination import CustomPagination
from apps.elasticsearch_app.queries.compay_builder_query import CompanySearchFilters
from apps.elasticsearch_app.search.global_search_document import (
    CompanyDocument,
)
from apps.elasticsearch_app.serializers.global_search_serializer import (
    CompanyListDocumentSerializer,
)
from apps.elasticsearch_app.services.global_search_service import GlobalSearchService


class PublicCompaniesView(generics.CreateAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = ()
    authentication_classes = ()


class ApplicantPublicCompanyView(BasePublicDocumentViewSet):
    document = CompanyDocument
    serializer_class = CompanyListDocumentSerializer
    pagination_class = CustomPagination

    filter_backends = [
        FilteringFilterBackend,
        DefaultOrderingFilterBackend,
    ]
    filter_fields = {
        "industry": "industry.raw",
        "city_id": "city_id",
    }

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="A search term",
            ),
            OpenApiParameter(
                name="industry",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Filter by industry name",
            ),
            OpenApiParameter(
                name="city_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Filter by city id",
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        required_filters = CompanySearchFilters.get_public_status_filter()
        keyword = self.request.query_params.get("search", "").strip()
        if not keyword:
            return (
                self.document.search()
                .query("match_all")
                .filter(required_filters)
                .sort({"jobs_open_count": {"order": "desc"}})
            )
        search_service = GlobalSearchService(
            search_term=keyword, user=self.request.user
        )

        # Get the initial search query from the service
        search_query = search_service.search_companies()

        # Apply the required filters to the search query
        return search_query.filter(required_filters).sort(
            {"jobs_open_count": {"order": "desc"}}
        )


class ApplicantCompanyView(RetrieveModelMixin, GenericViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = []

    def retrieve(self, request, *args, **kwargs):
        logo_value = Subquery(
            FileModel.objects.values("id").filter(
                ref_id=Cast(OuterRef("pk"), output_field=CharField()),
                ref_type=RefType.COMPANY_LOGO,
            )[:1]
        )
        instance = (
            Company.objects.filter(pk=kwargs.get("pk"))
            .annotate(logo=logo_value)
            .first()
        )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class VerifiedCompaniesListView(BaseListAPIView):
    queryset = Company.objects.all()
    serializer_class = CompaniesListSerializer
    permission_classes = []

    def get_queryset(self):
        current_date = timezone.now().date()

        return (
            super()
            .get_queryset()
            .filter(status=Status.APPROVED, is_active=True)
            .annotate(
                job_count=Count(
                    "jobpostmodel",
                    filter=Q(jobpostmodel__status="ACTIVE")
                    & Q(jobpostmodel__expire_date__gte=current_date),
                )
            )
        )


class CompanyIntegrationTabView(CustomJWTRequestMixin, APIView):
    """
    GET  /api/recruiter/company/integration  — read integration tab state
    PATCH /api/recruiter/company/integration  — save integrate_domain

    Resolves the company from the authenticated user's JWT (company_id claim).
    Returns integration partner connection status alongside the domain field so
    the frontend can render the Connect section without a second request.
    """

    permission_classes = [IsAuthenticated]

    def _get_company(self) -> Company:
        company_id = self.request.auth.payload.get("company_id")
        if not company_id:
            raise BadRequestException("No active company in session.")
        company = Company.objects.filter(id=company_id).first()
        if not company:
            raise NotFoundException("Company not found.")
        return company

    def get(self, request, *args, **kwargs):
        company = self._get_company()
        serializer = CompanyIntegrationTabSerializer(company, context={"request": request})
        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        company = self._get_company()
        serializer = CompanyIntegrationTabSerializer(
            company,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        """
        Recruiter-initiated disconnect from the ConnectJob integration tab.
        Notifies Wing Digital via their disconnect endpoint, then marks the
        local IntegrationPartner as disconnected regardless of ERP response.
        """
        from django.db import transaction
        from apps.integration.models.job_platform import IntegrationPartner
        from apps.integration.constants import ConnectorStatus

        company = self._get_company()

        with transaction.atomic():
            partner = (
                IntegrationPartner.objects.select_for_update()
                .filter(
                    organization_id=str(company.id),
                    status=ConnectorStatus.ACTIVE,
                )
                .first()
            )

            if not partner:
                return Response(
                    {"status": "error", "message": "No active integration found."},
                    status=http_status.HTTP_404_NOT_FOUND,
                )

            # Notify the ERP server-to-server so it can clean up its side.
            # Use partner_inbound_key (Key_Alpha) — the key ConnectJob uses to
            # authenticate outbound calls to Wing Digital.
            try:
                import requests as http
                erp_disconnect_url = (
                    f"{settings.CONNECTOR_INTEGRATION_URL}"
                    f"/api/connector-integration/disconnect"
                )
                http.post(
                    erp_disconnect_url,
                    headers={"X-CONNECTOR-KEY": partner.partner_inbound_key},
                    timeout=10,
                )
            except Exception:
                # ERP notification is best-effort; always disconnect locally.
                pass

            partner.status = ConnectorStatus.DISCONNECTED
            partner.save(update_fields=["status", "updated_at"])

        return Response(
            {"status": "success", "message": "Integration disconnected."},
            status=http_status.HTTP_200_OK,
        )
