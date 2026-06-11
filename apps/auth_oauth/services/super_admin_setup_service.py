import logging
from datetime import datetime
from django.db import transaction

from apps.auth_oauth.constants.auth_constants import DefaultRole, UserState, UserStatus
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.services.user_company_profile_service import UserCompanyProfileService
from apps.auth_oauth.services.user_profile_service import UserProfileService
from apps.auth_oauth.utils.auth_util import get_default_role
from apps.base.constants.base_constants import Status
from apps.base.models.company_model import Company
from config.settings.base import DEFAULT_PASSWORD

logger = logging.getLogger(__name__)


class SuperAdminSetupService:

    @classmethod
    @transaction.atomic
    def create_or_update_super_admin(cls, username, email):
        logger.info("Starting super admin create/update process...")

        # -----------------------------------------------------
        # 1. CREATE OR UPDATE USER
        # -----------------------------------------------------
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "first_name": "Job",
                "last_name": "Platform",
                "email": email,
                "is_staff": True,
                "is_active": True,
                "password": DEFAULT_PASSWORD,
                "date_joined": datetime.now(),
                "login_type": "pwd",
                "status": "active",
                "password_expired": datetime.now(),
                "is_send_email": True,
                "is_password_lock": False,
                "is_password_expired": False,
                "is_lock": False,
                "is_expired": False,
                "is_disable": False,
                "is_two_step_verification": False,
                "number_of_created": 1,
                "is_login": True,
                "is_required_reset_pwd": False,
                "otp_sent_count": 0,
            },
        )

        if created:
            user.set_password(DEFAULT_PASSWORD)
            user.save()
            logger.info("Super admin created")
        else:
            logger.info("Super admin exists — updating fields")
            update_data = {
                "first_name": "Job",
                "last_name": "Platform",
                "email": email,
                "is_staff": True,
                "is_active": True,
                "login_type": "pwd",
                "status": "active",
                "is_send_email": True,
                "is_password_lock": False,
                "is_password_expired": False,
                "is_lock": False,
                "is_expired": False,
                "is_disable": False,
                "is_two_step_verification": False,
                "is_required_reset_pwd": False,
            }

            for field, value in update_data.items():
                setattr(user, field, value)

            user.set_password(DEFAULT_PASSWORD)
            user.save()

        company = Company.objects.filter(
            name="Wing career",
            code="DEFAULT",
            is_active=True
        ).first()
        
        # -----------------------------------------------------
        # 2. PROFILE
        # -----------------------------------------------------
        profile = UserProfileService().get_by_id(user.pk)
        profile_data = {
            "user": user.pk,
            "first_name": "Job",
            "last_name": "Platform",
            "date_of_birth": "1998",
            "gender": "male",
            "phone_number": "099 911 917",
            "current_position": "Operator",
            "company": company.pk,
            "status": Status.APPROVED,
            "profile_type": "super_admin",
            "request_type": None,
            "submitted_date": datetime.now(),
        }

        if profile:
            logger.info("Updating super admin profile")
            profile = UserProfileService().update(profile, profile_data)
        else:
            logger.info("Creating super admin profile")
            profile = UserProfileService().create(profile_data)

        # -----------------------------------------------------
        # 3. USER COMPANY PROFILE
        # -----------------------------------------------------
        
        user_company = (
            UserCompanyProfileService.get_by_user(
                user.pk,
                company=company.pk,
                profile_type="super_admin",
            )
            or UserCompanyProfileService.get_by_user(
                user.pk,
                company=None,
                profile_type="super_admin",
            )
        )
        company_data = {
            "user": user.pk,
            "status": UserStatus.ACTIVE,
            "type": "super_admin",
            "company": company.pk,
            "profile": profile.pk,
            "state": UserState.COMPLETE_SETUP_PROFILE,
        }

        if user_company:
            logger.info("Updating super admin company profile")
            user_company = UserCompanyProfileService.update_profile_relation(
                profile_id=profile.pk,
                company_id=company.pk,
                user_company_profile_id=user_company.pk,
            )
        else:
            logger.info("Creating super admin company profile")
            user_company = UserCompanyProfileService.create(company_data)

        # -----------------------------------------------------
        # 4. ASSIGN ROLES
        # -----------------------------------------------------
        default_role = get_default_role(code=DefaultRole.OPERATOR_DEFAULT_ROLE)

        if user_company:
            user_company.roles.set(default_role)
            logger.info("Assigned default roles to super admin")

        logger.info("Super admin setup completed successfully")
        return user
