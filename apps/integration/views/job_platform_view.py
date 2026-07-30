import secrets
from datetime import timedelta
from urllib.parse import urlencode
from django.conf import settings

import requests
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.integration.constants import ConnectorStatus
from apps.integration.models.job_platform import (
    IntegrationHandshake,
    IntegrationPartner,
)
from apps.integration.serializers.integration_serializer import TokenExchangeSerializer
from apps.integration.utils.crypto_utils import hash_sha256, base64url_encode_sha256
from apps.integration.utils.mapping_utils import seed_default_field_mappings
from apps.base.mixins.custom_jwt_request_mixin import CustomJWTRequestMixin


class IntegrationExchangeView(CustomJWTRequestMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TokenExchangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        code_verifier = request.headers.get("X-Code-Verifier")

        if not code_verifier:
            return Response(
                {"status": "error", "message": "Missing code verifier."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            handshake = (
                IntegrationHandshake.objects.select_for_update()
                .filter(
                    temporary_code=data["temporary_code"],
                )
                .first()
            )

            if not handshake:
                return Response(
                    {"status": "error", "message": "Handshake not found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if handshake.expires_at <= timezone.now():
                handshake.delete()
                return Response(
                    {"status": "error", "message": "Handshake expired."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if handshake.state != data["state"]:
                return Response(
                    {"status": "error", "message": "State mismatch."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if base64url_encode_sha256(code_verifier) != handshake.code_challenge:
                return Response(
                    {"status": "error", "message": "PKCE verification failed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            key_beta = f"job_outbound_{secrets.token_hex(32)}"

            # Resolve the ERP domain from the company's integrate_domain so each
            # company can connect to its own ERP instance (multi-tenant support).
            from apps.base.models.company_model import Company
            company = Company.objects.filter(pk=handshake.organization_id).first()
            erp_domain = (
                (company.integrate_domain or "").rstrip("/")
                if company
                else ""
            ) or settings.CONNECTOR_INTEGRATION_URL.rstrip("/")

            erp_response = requests.post(
                f"{erp_domain}/api/connector-integration/finalize",
                json={
                    "authorization_code": data["authorization_code"],
                    "temporary_code": data["temporary_code"],
                    "state": data["state"],
                    "job_platform_org_id": handshake.organization_id,
                    "key_beta": key_beta,
                },
                timeout=10,
            )

            if erp_response.status_code != 200:
                return Response(
                    {
                        "status": "error",
                        "message": "Wing Digital finalize failed.",
                        "details": erp_response.text,
                    },
                    status=erp_response.status_code,
                )

            erp_data = erp_response.json()

            key_alpha = erp_data.get("key_alpha")
            erp_company_id = erp_data.get("erp_company_id")

            if not key_alpha or not erp_company_id:
                return Response(
                    {"status": "error", "message": "Invalid ERP finalize response."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            partner = IntegrationPartner.objects.create(
                organization_id=handshake.organization_id,
                partner_tenant_id=erp_company_id,
                erp_domain=erp_domain,
                # ERP -> ConnectJob
                partner_outbound_key=key_beta,
                partner_outbound_hash=hash_sha256(key_beta),
                # ConnectJob -> ERP
                partner_inbound_key=key_alpha,
                status=ConnectorStatus.ACTIVE,
            )

            # Seed the standard field mappings so the admin sees a ready-to-use
            # Data Mapping page immediately after connecting.
            seed_default_field_mappings(partner)

            handshake.delete()

        return Response(
            {
                "status": "success",
                "message": "Integration connected successfully.",
            },
            status=status.HTTP_200_OK,
        )




class InitializeHandshakeView(CustomJWTRequestMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.base.models.company_model import Company

        organization_id = str(self.request.company_id)

        if IntegrationPartner.objects.filter(
            organization_id=organization_id,
            status=ConnectorStatus.ACTIVE,
        ).exists():
            return Response(
                {"status": "error", "message": "Organization already integrated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Resolve the ERP domain from the company's integrate_domain field.
        # The company must have integrate_domain set before starting the handshake.
        company = Company.objects.filter(pk=organization_id).first()
        if not company:
            return Response(
                {"status": "error", "message": "Company not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        erp_domain = (company.integrate_domain or "").rstrip("/")
        if not erp_domain:
            return Response(
                {
                    "status": "error",
                    "message": "Company does not have an ERP domain configured. "
                               "Set integrate_domain on the company first.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        IntegrationHandshake.objects.filter(organization_id=organization_id).delete()

        temporary_code = f"code_{secrets.token_hex(24)}"
        state = f"state_{secrets.token_hex(24)}"
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64url_encode_sha256(code_verifier)

        # After the user accepts on the ERP the browser is redirected here,
        # bringing them back to ConnectJob's integration tab with the result.
        redirect_uri = (
            f"{settings.WEB_BASE_URL}/recruiter/company/integration/callback"
            f"?state={state}"
        )

        IntegrationHandshake.objects.create(
            temporary_code=temporary_code,
            state=state,
            code_challenge=code_challenge,
            organization_id=organization_id,
            redirect_uri=redirect_uri,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        # URL-encode redirect_uri so it survives cleanly as a query parameter
        # inside the authorize URL (it contains its own query string).
        authorize_params = urlencode({
            "client_id": "job_platform_id",
            "temporary_code": temporary_code,
            "state": state,
            "code_challenge": code_challenge,
            "redirect_uri": redirect_uri,
        })
        # Use the company's own ERP domain, not the global setting.
        authorize_url = (
            f"{erp_domain}/api/oauth/authorize"
            f"?{authorize_params}"
        )

        return Response(
            {
                "status": "success",
                "state": state,
                "code_verifier": code_verifier,
                "temporary_code": temporary_code,
                "authorize_url": authorize_url,
                "redirect_uri": redirect_uri,
                "erp_domain": erp_domain,
            },
            status=status.HTTP_201_CREATED,
        )


class JobCategoryLookupView(CustomJWTRequestMixin, APIView):
    """
    GET /api/v1/integration/look_up/categories

    Returns ConnectJob's own job category list so the Data Mapping UI can
    populate the Source Value dropdown for the 'category' field.
    Also proxies to the ERP to fetch their category list for the Target Value
    dropdown when ?side=erp is passed.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        side = request.query_params.get("side", "connectjob")

        if side == "erp":
            return self._fetch_erp_categories(request)

        return self._fetch_connectjob_categories()

    def _fetch_connectjob_categories(self):
        from apps.job_management_app.models.job_category_model import JobCategoryModel

        categories = (
            JobCategoryModel.objects
            .filter(is_deleted=False, is_active=True)
            .values("id", "name", "code")
            .order_by("name")
        )
        return Response({"data": list(categories)})

    def _fetch_erp_categories(self, request):
        organization_id = str(request.company_id)
        from apps.integration.models.job_platform import IntegrationPartner
        from apps.integration.constants import ConnectorStatus

        partner = IntegrationPartner.objects.filter(
            organization_id=organization_id,
            status=ConnectorStatus.ACTIVE,
        ).first()

        if not partner:
            return Response(
                {"status": "error", "message": "No active integration found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            erp_base = (partner.erp_domain or settings.CONNECTOR_INTEGRATION_URL).rstrip("/")
            erp_response = requests.get(
                f"{erp_base}/api/connector-integration/categories",
                headers={"X-CONNECTOR-KEY": partner.partner_inbound_key},
                timeout=10,
            )
        except requests.RequestException as exc:
            return Response(
                {"status": "error", "message": "ERP server could not be reached.", "details": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if erp_response.status_code != 200:
            return Response(
                {"status": "error", "message": "ERP rejected category lookup.", "details": erp_response.text},
                status=erp_response.status_code,
            )

        return Response(erp_response.json(), status=status.HTTP_200_OK)


class ErpUserLookupProxyView(CustomJWTRequestMixin, APIView):
    """
    ConnectJob frontend calls this endpoint.

    This view calls Wing Digital server-to-server.
    Frontend never sees integration keys.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        organization_id = str(self.request.company_id)

        try:
            partner = IntegrationPartner.objects.get(
                organization_id=organization_id,
                status="active",
            )
        except IntegrationPartner.DoesNotExist:
            return Response(
                {
                    "status": "error",
                    "message": "Integration is not active.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Key Alpha: ConnectJob -> Wing Digital
        inbound_key = partner.partner_inbound_key
        erp_company_id = partner.partner_tenant_id

        erp_api_url = f"{(partner.erp_domain or settings.CONNECTOR_INTEGRATION_URL).rstrip('/')}/api/connector-integration/users"

        try:
            erp_response = requests.get(
                url=erp_api_url,
                headers={
                    "X-CONNECTOR-KEY": f"{inbound_key}",
                },
                params={
                    "company_id": erp_company_id,
                    "paging": True,
                },
                timeout=10,
            )
        except requests.RequestException as exc:
            return Response(
                {
                    "status": "error",
                    "message": "Wing Digital server could not be reached.",
                    "details": str(exc),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if erp_response.status_code != 200:
            return Response(
                {
                    "status": "error",
                    "message": "Wing Digital rejected user lookup request.",
                    "details": erp_response.text,
                },
                status=erp_response.status_code,
            )

        return Response(
            erp_response.json(),
            status=status.HTTP_200_OK,
        )


class DropIntegrationView(CustomJWTRequestMixin, APIView):  # noqa: E302
    """
    POST /api/v1/integration/disconnect
    Called server-to-server by the ERP backend (Wing Digital) when the
    user clicks "Disconnect" in the ERP's Integration tab.
    Auth: X-CONNECTOR-KEY header carrying Key_Beta (partner_outbound_key).
    """

    permission_classes = [AllowAny]

    def post(self, request):
        connector_key = request.headers.get("X-CONNECTOR-KEY")

        if not connector_key:
            return Response(
                {"status": "error", "message": "Missing connector key."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        incoming_hash = hash_sha256(connector_key)

        with transaction.atomic():
            partner = (
                IntegrationPartner.objects.select_for_update()
                .filter(partner_outbound_hash=incoming_hash, status=ConnectorStatus.ACTIVE)
                .first()
            )

            if not partner:
                return Response(
                    {"status": "error", "message": "Invalid connector key."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            partner.status = ConnectorStatus.DISCONNECTED
            partner.save(update_fields=["status", "updated_at"])

        return Response(
            {
                "status": "success",
                "message": "ConnectJob integration disconnected.",
            },
            status=status.HTTP_200_OK,
        )
