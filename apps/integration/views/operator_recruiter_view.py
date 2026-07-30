import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auth_oauth.constants.auth_constants import UserTypes
from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.models.role_model import Role
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.base.constants.base_constants import Status
from apps.base.mixins.custom_jwt_request_mixin import CustomJWTRequestMixin
from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.models.company_model import Company
from apps.integration.constants import ConnectorStatus
from apps.integration.models.job_platform import IntegrationPartner, IntegrationUserMapping
from apps.integration.serializers.operator_recruiter_serializer import OperatorIntegrationRecruiterSerializer

logger = logging.getLogger(__name__)
User = get_user_model()


class OperatorIntegrationRecruiterView(PermissionMixin, CustomJWTRequestMixin, APIView):
    """
    POST /api/v1/integration/operator/companies/{company_id}/recruiter

    Operator creates an admin recruiter account for an integration company by
    selecting a user from the Connect ERP user list
    (fetched via GET /api/v1/integration/look_up/users).

    Flow:
      1. Validate company exists and has an ACTIVE IntegrationPartner.
      2. Resolve or create User + Profile.
      3. Create UserCompanyProfile (admin_recruiter type).
         → Existing signal fires: sync_recruiter_to_erp.delay(ucp.id)
         → IntegrationUserMapping is written with the ERP's user ID pre-populated.
      4. Return the new user + UCP summary.
    """

    permission_classes = [IsAuthenticated]
    permission_codename = "operator_manage_user"

    def post(self, request, company_id):
        # ── Validate company ──────────────────────────────────────────────────
        company = Company.objects.filter(pk=company_id, is_active=True).first()
        if not company:
            return Response(
                {"status": "error", "message": f"Company id={company_id} not found or inactive."},
                status=status.HTTP_404_NOT_FOUND,
            )

        partner = IntegrationPartner.objects.filter(
            organization_id=str(company.id),
            status=ConnectorStatus.ACTIVE,
        ).first()
        if not partner:
            return Response(
                {"status": "error", "message": "This company has no active ERP integration."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Validate input ────────────────────────────────────────────────────
        serializer = OperatorIntegrationRecruiterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        email = data["email"]
        erp_user_id = data["erp_user_id"]
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        phone_number = data.get("phone_number")
        role_type = data.get("role_type", UserTypes.ADMIN_RECRUITER.value)

        with transaction.atomic():
            # ── Resolve or create User ────────────────────────────────────────
            user = User.objects.filter(email=email, is_active=True).first()
            created_user = False
            if not user:
                user = User.objects.create_user(
                    email=email,
                    username=email,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=True,
                )
                created_user = True

            # ── Resolve or create Profile ─────────────────────────────────────
            # Scoped to (user, company) — matching OperatorAssignRolesSerializer's
            # invariant that each company membership gets its own Profile, since
            # a ConnectJob user can hold a UserCompanyProfile (and therefore a
            # distinct Profile) in more than one company.
            profile, _ = Profile.objects.get_or_create(
                user=user,
                company=company,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "full_name": f"{first_name} {last_name}".strip(),
                    "phone_number": phone_number,
                    "profile_type": role_type,
                    "status": Status.COMPLETE,
                },
            )

            # ── Guard: UCP already exists for this company ────────────────────
            existing_ucp = UserCompanyProfile.objects.filter(
                user=user,
                company=company,
            ).first()
            if existing_ucp:
                return Response(
                    {
                        "status": "error",
                        "message": "User already has a profile in this company.",
                        "ucp_id": existing_ucp.id,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # ── Resolve role ──────────────────────────────────────────────────
            role = Role.objects.filter(type=role_type).first()

            # ── Create UserCompanyProfile ─────────────────────────────────────
            ucp = UserCompanyProfile.objects.create(
                user=user,
                profile=profile,
                company=company,
                type=role_type,
                status="complete_setup_profile",
                state="complete_setup_profile",
            )
            if role:
                ucp.roles.add(role)

            # ── Pre-populate IntegrationUserMapping with ERP user ID ──────────
            # The post_save signal (on_recruiter_created) will also fire and
            # call sync_recruiter_to_erp.delay(ucp.id) which normally creates
            # the mapping with partner_user_id=None, then fills it in after ERP
            # responds. Since we already KNOW the ERP user ID here, we write the
            # mapping directly so it is available immediately.
            IntegrationUserMapping.objects.update_or_create(
                connection=partner,
                local_user_id=str(profile.id),
                defaults={
                    "partner_user_id": str(erp_user_id),
                    "user_company_profile": ucp,
                },
            )

        logger.info(
            "OperatorIntegrationRecruiter: created ucp_id=%s user_id=%s company_id=%s erp_user_id=%s",
            ucp.id,
            user.id,
            company.id,
            erp_user_id,
        )

        return Response(
            {
                "status": "success",
                "message": "Admin recruiter created successfully.",
                "user_id": user.id,
                "profile_id": profile.id,
                "ucp_id": ucp.id,
                "email": email,
                "company_id": company.id,
                "erp_user_id": erp_user_id,
                "created_user": created_user,
            },
            status=status.HTTP_201_CREATED,
        )
