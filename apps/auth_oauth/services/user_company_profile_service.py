from apps.auth_oauth.constants.auth_constants import ProfileStatus, UserState, UserTypes
from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.auth_oauth.serializers.user_company_profile_serializer import (
    UserCompanyProfileSerializer,
)
from apps.auth_oauth.services.user_role_service import UserRoleService
from apps.auth_oauth.tasks import mirror_social_image_to_storage


class UserCompanyProfileService:

    @staticmethod
    def create(data):
        serializer = UserCompanyProfileSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return instance

    @staticmethod
    def get_by_user_and_company(user_id: int, company_id: int):
        return (
            UserCompanyProfile.objects
            .select_related("company", "profile")
            .prefetch_related("roles")
            .filter(user_id=user_id, company_id=company_id)
            .order_by("-id")
            .first()
        )

    @staticmethod
    def update_profile_relation(
            profile_id=None,
            company_id=None,
            user_company_profile_id=None,
    ):
        UserCompanyProfile.objects.filter(id=user_company_profile_id).update(
            profile_id=profile_id,
            company_id=company_id,
            state=UserState.COMPLETE_SETUP_PROFILE,
        )

    @staticmethod
    def get_by_code(user_id, code=None):
        return UserCompanyProfile.objects.filter(user_id=user_id, code=code).first()

    @staticmethod
    def get_by_user(user, company, profile_type):
        return UserCompanyProfile.objects.filter(
            user=user, company=company, type=profile_type
        ).first()

    @staticmethod
    def delete_remove_user(users, company, profile_type):
        if users is None or users == []:
            return 0
        UserCompanyProfile.objects.filter(company=company, type=profile_type).exclude(
            user__in=users
        ).delete()

    @staticmethod
    def create_or_update(data, **kwargs):

        user = kwargs.get("user", None)
        company = kwargs.get("company", None)
        profile_type = kwargs.get("profile_type", None)
        instance = UserCompanyProfile.objects.filter(
            user=user, company=company, type=profile_type
        ).first()
        serializer = UserCompanyProfileSerializer(data=data, instance=instance)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return instance

    @staticmethod
    def social_create(data):
        image_url = data.pop("image_url")
        filter_data = data.copy()
        filter_data.pop("company", None)
        filter_data.pop("type", None)
        filter_data.pop("provider", None)
        user = data.pop("user")
        data['user'] = user.pk
        instance = UserCompanyProfile.objects.filter(**filter_data).first()
        if not instance:
            serializer = UserCompanyProfileSerializer(data=data, instance=instance)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
        if instance.profile is None:
            profile_instance = Profile.objects.create(
                first_name=instance.user.first_name,
                last_name=instance.user.last_name,
                email=instance.user.email,
                profile_type=instance.type,
                user=instance.user
            )
            instance.profile = profile_instance
            instance.save(update_fields=['profile'])
        mirror_social_image_to_storage.apply_async(
            kwargs={
                "profile_id": instance.profile.pk,
                "image_url": image_url,
            }
        )
        if not instance.roles.exists():
            defaults = list(UserRoleService.get_social_default_roles(instance.type))
            if defaults:
                instance.roles.add(*defaults)
        return instance

    @staticmethod
    def delete_associate_user_company(user_company_profile_id):
        UserCompanyProfile.objects.filter(id=user_company_profile_id).delete()

    @staticmethod
    def get_by_userid(user_id, profile_type):
        return UserCompanyProfile.objects.filter(
            user_id=user_id, type=profile_type, status=ProfileStatus.ACTIVE
        ).last()

    @staticmethod
    def get_by_id(user_company_profile_id):
        return UserCompanyProfile.objects.filter(
            id=user_company_profile_id
        ).first()

    @staticmethod
    def get_all_by_user_id(user_id):
        return UserCompanyProfile.objects.filter(
            user_id=user_id, status=ProfileStatus.ACTIVE
        )
    @staticmethod
    def has_applicant(user_id):
        return UserCompanyProfile.objects.filter(
            user_id=user_id,
            type=UserTypes.APPLICANT.value,
            status=ProfileStatus.ACTIVE,
        ).exists()
    @staticmethod
    def has_recruiter(user_id):
        return UserCompanyProfile.objects.filter(
            user_id=user_id,
            type__in=[
                UserTypes.RECRUITER.value,
                UserTypes.ADMIN_RECRUITER.value,
            ],
            status=ProfileStatus.ACTIVE,
        ).exists()
