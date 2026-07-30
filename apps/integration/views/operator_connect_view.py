import logging
import secrets

import requests
from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.base.mixins.custom_jwt_request_mixin import CustomJWTRequestMixin
from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.models.company_model import Company
from apps.integration.constants import ConnectorStatus
from apps.integration.models.job_platform import IntegrationPartner
from apps.integration.serializers.operator_connect_serializer import OperatorConnectSerializer
from apps.integration.services.company_integration_service import CompanyIntegrationService
from apps.integration.utils.crypto_utils import hash_sha256
from apps.integration.utils.mapping_utils import seed_default_field_mappings

logger = logging.getLogger(__name__)


class OperatorConnectView(PermissionMixin, CustomJWTRequestMixin, APIView):
    """
    POST /api/v1/integration/operator/connect

    Operator-initiated server-to-server connection with a Connect ERP instance.

    Flow:
      1. Validate request (domain + company).
      2. Guard: block if an ACTIVE partner already exists for this company/domain.
      3. Generate Key_Beta (ConnectJob → ERP key).
      4. Call ERP's /api/connector-integration/operator-connect endpoint.
      5. On success: create or link Company, create IntegrationPartner, seed field mappings.
    """

    permission_classes = [IsAuthenticated]
    permission_codename = "operator_manage_company"

    def post(self, request):
        serializer = OperatorConnectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        erp_domain = data["erp_domain"]
        company_id = data.get("company_id")
        company_name = data.get("company_name", "").strip()

        # ── 1. Resolve or prepare company ─────────────────────────────────────
        company = None
        if company_id:
            company = Company.objects.filter(pk=company_id).first()
            if not company:
                return Response(
                    {"status": "error", "message": f"Company id={company_id} not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # ── 2. Guard: already connected? ──────────────────────────────────────
        if company:
            already = IntegrationPartner.objects.filter(
                organization_id=str(company.id),
                status=ConnectorStatus.ACTIVE,
            ).exists()
            if already:
                return Response(
                    {"status": "error", "message": "This company already has an active integration."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        domain_taken = IntegrationPartner.objects.filter(
            status=ConnectorStatus.ACTIVE,
        ).select_related().exists() and CompanyIntegrationService.get_by_domain(erp_domain) is not None

        if domain_taken:
            existing_company = CompanyIntegrationService.get_by_domain(erp_domain)
            if existing_company:
                already = IntegrationPartner.objects.filter(
                    organization_id=str(existing_company.id),
                    status=ConnectorStatus.ACTIVE,
                ).exists()
                if already:
                    return Response(
                        {"status": "error", "message": "This ERP domain already has an active integration."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        # ── 3. Generate Key_Beta ───────────────────────────────────────────────
        key_beta = f"job_outbound_{secrets.token_hex(32)}"
        org_id_hint = str(company.id) if company else str(secrets.token_hex(8))

        # ── 4. Call ERP ────────────────────────────────────────────────────────
        try:
            erp_response = requests.post(
                f"{erp_domain}/api/connector-integration/operator-connect",
                json={
                    "connectjob_org_id": org_id_hint,
                    "key_beta": key_beta,
                    "platform": "connectjob",
                },
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.error("OperatorConnect: ERP unreachable domain=%s error=%s", erp_domain, exc)
            return Response(
                {"status": "error", "message": "Connect ERP could not be reached.", "details": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if erp_response.status_code != 200:
            return Response(
                {
                    "status": "error",
                    "message": "Connect ERP rejected the connection request.",
                    "details": erp_response.text,
                },
                status=erp_response.status_code,
            )

        erp_data = erp_response.json()
        key_alpha = erp_data.get("key_alpha")
        erp_company_id = erp_data.get("erp_company_id")
        company_info = erp_data.get("company_info", {})

        if not key_alpha or not erp_company_id:
            return Response(
                {"status": "error", "message": "Invalid response from Connect ERP (missing key_alpha or erp_company_id)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── 5. Persist ─────────────────────────────────────────────────────────
        with transaction.atomic():
            if not company:
                company = CompanyIntegrationService.register({
                    "name": company_name or company_info.get("name", erp_domain),
                    "integrate_domain": erp_domain,
                    **{k: v for k, v in company_info.items() if k in (
                        "email", "website", "phone_number", "address", "about_me",
                        "industry", "company_size", "profile_picture_id",
                    )},
                })
            else:
                company.integrate_domain = erp_domain
                company.is_integrate = True
                company.save(update_fields=["integrate_domain", "is_integrate"])

            partner = IntegrationPartner.objects.create(
                organization_id=str(company.id),
                partner_tenant_id=erp_company_id,
                partner_outbound_key=key_beta,
                partner_outbound_hash=hash_sha256(key_beta),
                partner_inbound_key=key_alpha,
                status=ConnectorStatus.ACTIVE,
            )

            seed_default_field_mappings(partner)

        logger.info(
            "OperatorConnect: SUCCESS company_id=%s erp_company_id=%s domain=%s",
            company.id,
            erp_company_id,
            erp_domain,
        )

        return Response(
            {
                "status": "success",
                "message": "Integration connected successfully.",
                "company_id": company.id,
                "partner_tenant_id": erp_company_id,
                "erp_domain": erp_domain,
            },
            status=status.HTTP_201_CREATED,
        )
