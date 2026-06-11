import secrets
from datetime import timedelta
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

            erp_response = requests.post(
                f"{settings.CONNECTOR_INTEGRATION_URL}/api/connector-integration/finalize",
                json={
                    "authorization_code": data["authorization_code"],
                    "temporary_code": data["temporary_code"],
                    "state": data["state"],
                    "job_platform_org_id": handshake.organization_id,
                    "key_beta": key_beta,
                },
                # timeout=10,
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

            IntegrationPartner.objects.create(
                organization_id=handshake.organization_id,
                partner_tenant_id=erp_company_id,
                # ERP -> ConnectJob
                partner_outbound_key=key_beta,
                partner_outbound_hash=hash_sha256(key_beta),
                # ConnectJob -> ERP
                partner_inbound_key=key_alpha,
                status=ConnectorStatus.ACTIVE,
            )

            handshake.delete()

        return Response(
            {
                "status": "success",
                "message": "Integration connected successfully.",
            },
            status=status.HTTP_200_OK,
        )


class DropIntegrationView(CustomJWTRequestMixin, APIView):
    """
    ENDPOINT 2: https://api.Integration.com/v1/integration/disconnect
    Called synchronously by the ERP backend to tear down integration lines.
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header or not auth_header.startswith("Bearer "):
            return Response(
                {"status": "error", "message": "Unauthorized"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        incoming_key_beta = auth_header.split(" ")[1]
        incoming_hash = hash_sha256(incoming_key_beta)
        with transaction.atomic():
            try:
                # O(1) indexed lookup instead of slow database text looping
                partner = IntegrationPartner.objects.select_for_update().get(
                    partner_outbound_hash=incoming_hash, status="active"
                )
                partner.delete()  # Cascades to user mapping tables
            except IntegrationPartner.DoesNotExist:
                return Response(
                    {"status": "error", "message": "Forbidden: Token invalid."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        return Response(
            {"status": "success", "message": "Connection terminated"},
            status=status.HTTP_200_OK,
        )


class InitializeHandshakeView(CustomJWTRequestMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        organization_id = str(self.request.company_id)

        if IntegrationPartner.objects.filter(
            organization_id=organization_id,
            status=ConnectorStatus.ACTIVE,
        ).exists():
            return Response(
                {"status": "error", "message": "Organization already integrated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        IntegrationHandshake.objects.filter(organization_id=organization_id).delete()

        temporary_code = f"code_{secrets.token_hex(24)}"
        state = f"state_{secrets.token_hex(24)}"
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64url_encode_sha256(code_verifier)

        redirect_uri = f"{settings.CONNECTOR_INTEGRATION_URL}/integration/callback"

        IntegrationHandshake.objects.create(
            temporary_code=temporary_code,
            state=state,
            code_challenge=code_challenge,
            organization_id=organization_id,
            redirect_uri=redirect_uri,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        authorize_url = (
            f"{settings.CONNECTOR_INTEGRATION_URL}/api/oauth/authorize"
            f"?client_id=job_platform_id"
            f"&temporary_code={temporary_code}"
            f"&state={state}"
            f"&code_challenge={code_challenge}"
            f"&redirect_uri={redirect_uri}"
        )

        return Response(
            {
                "status": "success",
                "state": state,
                "code_verifier": code_verifier,
                "temporary_code": temporary_code,
                "authorize_url": authorize_url,
                "redirect_uri": redirect_uri,
            },
            status=status.HTTP_201_CREATED,
        )


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

        erp_api_url = f"{settings.CONNECTOR_INTEGRATION_URL}/api/connector-integration/users"

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
                # timeout=10,
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


class DropIntegrationView(CustomJWTRequestMixin, APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        connector_key = request.headers.get("X-CONNECTOR-KEY")

        if not connector_key:
            return Response(
                {
                    "status": "error",
                    "message": "Missing connector key.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        incoming_hash = hash_sha256(connector_key)

        partner = IntegrationPartner.objects.filter(
            partner_outbound_hash=incoming_hash,
            status="active",
        ).first()

        if not partner:
            return Response(
                {
                    "status": "error",
                    "message": "Invalid connector key.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        partner.status = "disconnected"
        partner.save(update_fields=["status"])

        return Response(
            {
                "status": "success",
                "message": "ConnectJob integration disconnected.",
            },
            status=status.HTTP_200_OK,
        )
