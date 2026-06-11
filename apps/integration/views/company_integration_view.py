from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.base.mixins.permission_mixin import PermissionMixin
from apps.integration.serializers.company_integration_serializer import (
    CompanyIntegrationDetailSerializer,
    CompanyIntegrationInboundSerializer,
    CompanyIntegrationSummarySerializer,
)
from apps.integration.services.company_integration_service import (
    CompanyIntegrationService,
)

# ---------------------------------------------------------------------------
# Mixins / helpers
# ---------------------------------------------------------------------------


def _get_company_or_404(company_id: int):
    company = CompanyIntegrationService.get_by_id(company_id)
    if not company:
        raise NotFound(detail=f"Integrated company id={company_id} not found.")
    return company


class CompanyIntegrationRegisterView(PermissionMixin, APIView):
    """
    POST /api/integrations/companies/register/

    External platform calls this once to onboard their company into our system.
    Idempotent on `integrate_domain`: if the domain already exists the view
    returns 200 with the existing record rather than raising a conflict, so
    callers can safely retry on network failures.
    """

    permission_classes = [IsAuthenticated]
    permission_codename = "operator_manage_company"

    def post(self, request):
        # Check if the domain already exists → treat as a sync instead
        domain = (request.data.get("integrate_domain") or "").lower().rstrip("/")
        existing = CompanyIntegrationService.get_by_domain(domain) if domain else None

        if existing:
            serializer = CompanyIntegrationInboundSerializer(
                data=request.data,
                context={"request": request, "instance": existing},
            )
            serializer.is_valid(raise_exception=True)
            company = CompanyIntegrationService.sync(
                existing, serializer.validated_data
            )
            out = CompanyIntegrationSummarySerializer(company)
            return Response(
                {
                    "detail": "Company already registered; record synced.",
                    "data": out.data,
                },
                status=status.HTTP_200_OK,
            )

        serializer = CompanyIntegrationInboundSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        company = CompanyIntegrationService.register(serializer.validated_data)
        out = CompanyIntegrationSummarySerializer(company)
        return Response(
            {"detail": "Company registered successfully.", "data": out.data},
            status=status.HTTP_201_CREATED,
        )


class CompanyIntegrationSyncView(PermissionMixin, APIView):
    """
    PATCH /api/integrations/companies/<id>/sync/

    External platform calls this whenever its company profile changes.
    Only fields included in the request body are updated (partial merge).
    Triggers an Elasticsearch re-index automatically.
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk: int):
        company = _get_company_or_404(pk)

        serializer = CompanyIntegrationInboundSerializer(
            data=request.data,
            context={"request": request, "instance": company},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        company = CompanyIntegrationService.sync(company, serializer.validated_data)
        out = CompanyIntegrationSummarySerializer(company)
        return Response(
            {"detail": "Company synced successfully.", "data": out.data},
            status=status.HTTP_200_OK,
        )


class CompanyIntegrationDetailView(PermissionMixin, APIView):
    """
    GET  /api/integrations/companies/<id>/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        company = _get_company_or_404(pk)
        out = CompanyIntegrationDetailSerializer(company)
        return Response({"data": out.data}, status=status.HTTP_200_OK)


class CompanyIntegrationListView(PermissionMixin, APIView):
    """
    GET /api/integrations/companies/

    Returns all active integrated companies ordered by creation date desc.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        companies = CompanyIntegrationService.list_active()
        out = CompanyIntegrationSummarySerializer(companies, many=True)
        return Response({"data": out.data}, status=status.HTTP_200_OK)


class CompanyIntegrationDeactivateView(PermissionMixin, APIView):
    """
    POST /api/integrations/companies/<id>/deactivate/

    Soft-disables the integrated company and removes it from ES search results.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        company = _get_company_or_404(pk)

        if not company.is_active:
            return Response(
                {"detail": "Company is already inactive."},
                status=status.HTTP_200_OK,
            )

        company = CompanyIntegrationService.deactivate(company)
        out = CompanyIntegrationSummarySerializer(company)
        return Response(
            {"detail": "Company deactivated.", "data": out.data},
            status=status.HTTP_200_OK,
        )


class CompanyIntegrationReactivateView(PermissionMixin, APIView):
    """
    POST /api/integrations/companies/<id>/reactivate/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        company = _get_company_or_404(pk)

        if company.is_active:
            return Response(
                {"detail": "Company is already active."},
                status=status.HTTP_200_OK,
            )

        company = CompanyIntegrationService.reactivate(company)
        out = CompanyIntegrationSummarySerializer(company)
        return Response(
            {"detail": "Company reactivated.", "data": out.data},
            status=status.HTTP_200_OK,
        )


class CompanyIntegrationLookupByDomainView(PermissionMixin, APIView):
    """
    GET /api/integrations/companies/lookup/?domain=example.com

    Convenience endpoint so partner platforms can check their own record
    using their domain rather than an internal DB id.
    """

    permission_classes = [IsAuthenticated]
    permission_codename = "operator_manage_company"

    def get(self, request):
        domain = request.query_params.get("domain", "").strip()
        if not domain:
            raise ValidationError({"domain": "This query parameter is required."})

        company = CompanyIntegrationService.get_by_domain(domain)
        if not company:
            raise NotFound(detail=f"No integrated company found for domain '{domain}'.")

        out = CompanyIntegrationDetailSerializer(company)
        return Response({"data": out.data}, status=status.HTTP_200_OK)
