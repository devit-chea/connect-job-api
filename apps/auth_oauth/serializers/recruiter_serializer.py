import logging
from datetime import datetime

from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models.query_utils import Q
from drf_extra_fields.relations import PresentablePrimaryKeyRelatedField
from environs import env
from rest_framework import serializers

from apps.auth_oauth.constants.auth_constants import (
    UserStatus,
    UserState,
    UserTypes,
    RecruiterSetupProfileStep,
    ProfileStatus,
    RequestType,
    DefaultRole,
)
from apps.auth_oauth.mixins.encryption_mixins import EncryptionMixin
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.serializers.alphanumeric_serializer import AlphanumericSerializer
from apps.auth_oauth.services.user_company_profile_service import (
    UserCompanyProfileService,
)
from apps.auth_oauth.services.user_service import UserService
from apps.auth_oauth.utils.auth_util import (
    get_full_name,
    get_default_role,
    get_active_profile_id,
)
from apps.base.constants.base_constants import Status
from apps.base.fields.date_filed import DateField
from apps.base.models.company_model import Company
from apps.base.models.country_model import Country
from apps.base.models.geo_area_model import GeoArea
from apps.base.serializers.base_serializer import BaseSerializer
from apps.base.serializers.country_serializer import CountryInfoSerializer
from apps.base.serializers.geo_area_serializer import GeoAreaInfoSerializer
from apps.base.services.company_service import CompanyService
from apps.base.utils.base_util import (
    is_valid_email,
    get_default_company,
    is_valid_phone_number,
)
from apps.base.utils.file_management_util import FileURLService
from apps.core.exceptions.base_exceptions import BadRequestException
from django.contrib.auth.password_validation import validate_password as django_validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
env.read_env()


logger = logging.getLogger(__name__)

# company profile
class CompanySerializer(serializers.ModelSerializer):

    def __init__(self, instance=None, step=None, data=..., **kwargs):
        self.step = step
        super().__init__(instance, data, **kwargs)

    city = PresentablePrimaryKeyRelatedField(
        queryset=GeoArea.objects.all(),
        presentation_serializer=GeoAreaInfoSerializer,
        required=False,
        allow_null=True,
    )
    country = PresentablePrimaryKeyRelatedField(
        queryset=Country.objects.all(),
        presentation_serializer=CountryInfoSerializer,
        required=False,
        allow_null=True,
    )
    name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    found_date = serializers.CharField(allow_blank=True, required=False)
    cover_picture_id = serializers.CharField(allow_blank=True, required=False)
    profile_picture_id = serializers.CharField(allow_blank=True, required=False)

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "industry",
            "company_size",
            "found_date",
            "address",
            "city",
            "country",
            "postal_code",
            "phone_number",
            "email",
            "linkedin_email",
            "website",
            "about_me",
            "is_agree_policy",
            "profile_picture_id",
            "cover_picture_id"
        ]
        extra_kwargs = {"id": {"read_only": True}}

    def to_internal_value(self, data):
        if self.step == RecruiterSetupProfileStep.RSP2:
            self.fields["name"] = serializers.CharField()
            self.fields["industry"] = serializers.CharField()
            self.fields["found_date"] = serializers.CharField()
            self.fields["cover_picture_id"] = serializers.CharField(required=False, allow_blank=True)
            self.fields["profile_picture_id"] = serializers.CharField(required=False, allow_blank=True)
        elif self.step == RecruiterSetupProfileStep.RSP3:
            self.fields["address"] = serializers.CharField()
            self.fields["city"] = PresentablePrimaryKeyRelatedField(
                queryset=GeoArea.objects.all(),
                presentation_serializer=GeoAreaInfoSerializer,
            )
            self.fields["country"] = PresentablePrimaryKeyRelatedField(
                queryset=Country.objects.all(),
                presentation_serializer=CountryInfoSerializer,
            )
            self.fields["phone_number"] = serializers.CharField()
            self.fields["email"] = serializers.EmailField()
            self.fields["about_me"] = serializers.CharField()

        return super().to_internal_value(data)


class RecruiterSignupSerializer(BaseSerializer):

    def __init__(self, instance=None, data=..., profile_type=None, **kwargs):
        self.profile_type = profile_type
        super().__init__(instance, data, **kwargs)

    class Meta:
        model = User
        fields = ["id", "username", "password"]
        extra_kwargs = {"id": {"read_only": True}, "password": {"write_only": True}}

    @transaction.atomic()
    def create(self, validated_data):
        username = validated_data.get("username")
        if is_valid_email(username):
            validated_data["email"] = username

        # todo: is_valid_phone_number(username)
        else:
            raise BadRequestException("invalid email.")
            # validated_data["email"] = str(username) + "@dummy.com"
        # if env.str("DJANGO_ENV") == ENV.DEV:
        #     number_of_created = UserValidation().validate_existed_email(
        #         validated_data.get("username")
        #     )
        #     validated_data["number_of_created"] = (
        #         number_of_created + 1 if number_of_created else 1
        #     )
        encrypted_password = validated_data.get("password")
        try:
            encryption = EncryptionMixin()
            password = encryption.decrypt_value(encrypted_password)
        except Exception:
            raise serializers.ValidationError(
                {"detail": "Unable to create the account."}
            )
        validated_data["status"] = UserStatus.ACTIVE
        validated_data["is_active"] = True
        validated_data["state"] = UserState.PENDING_VERIFY_OPT
        validated_data["password"] = make_password(password)
        user = super().create(validated_data)

        dup_q = (
                Q(state=UserState.PENDING_VERIFY_OPT) &
                (Q(username__iexact=user.username) & Q(email__iexact=user.email))
        )
        _ = (
            User.objects
            .filter(dup_q)
            .exclude(pk=user.pk)
            .update(
                is_active=False,
                status=UserStatus.INACTIVE,
            )
        )

        default_company = get_default_company()
        default_company_id = (
            default_company.pk
            if default_company and self.profile_type == UserTypes.APPLICANT
            else None
        )
        data = {
            "user": user.pk,
            "status": ProfileStatus.ACTIVE,
            "type": self.profile_type,
            "state": UserState.PENDING_VERIFY_OPT,
            "company": default_company_id,
        }

        user_company_profile_instance = UserCompanyProfileService.create(data)
        default_role = []
        if self.profile_type == UserTypes.RECRUITER:
            default_role = get_default_role(code=DefaultRole.RECRUITER_ROLE)
        elif self.profile_type == UserTypes.ADMIN_RECRUITER:
            default_role = get_default_role(code=DefaultRole.PENDING_ADMIN_RECRUITER_ROLE)
        else:
            default_role = get_default_role(code=DefaultRole.APPLICANT_ROLE)

        user_company_profile_instance.roles.set(default_role)
        if not user.default_user_profile_company:
            user.default_user_profile_company = user_company_profile_instance.pk if user_company_profile_instance else None
            user.is_login = True
            user.save()

        return user

    def validate_password(self, password):
        """
        Applies all validators defined in settings.AUTH_PASSWORD_VALIDATORS,
        including your CustomPasswordValidator.
        """
        user = self.instance or self.Meta.model()

        try:
            django_validate_password(password, user=user)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))

        return password


class RecruiterProfileSignupSerializer(BaseSerializer):
    company_profile = CompanySerializer(
        write_only=True, required=False, allow_null=True
    )
    step = serializers.CharField(write_only=True)

    date_of_birth = DateField(allow_blank=True, required=False)

    class Meta:
        model = Profile
        fields = [
            "id",
            "first_name",
            "last_name",
            "gender",
            "date_of_birth",
            "phone_number",
            "current_position",
            "step",
            "company_profile",
            "cover_picture_id",
            "profile_picture_id"
        ]
        extra_kwargs = {
            "submitted_date": {"read_only": True},
            "id": {"read_only": True},
        }

    def validate(self, attrs):
        request = self.context.get("request")
        _, ucp_id = get_active_profile_id(request)
        ucp = UserCompanyProfileService().get_by_id(ucp_id)
        if not ucp:
            raise serializers.ValidationError("Active profile not found.")
        if ucp.type not in (UserTypes.RECRUITER, UserTypes.ADMIN_RECRUITER):
            raise serializers.ValidationError("This endpoint is only for recruiter setup.")
        if getattr(ucp, "state", None) != "pending_setup_profile":
            raise serializers.ValidationError("You have already completed recruiter setup.")
        return attrs

    def to_internal_value(self, data):
        step = data.get("step", None)
        if step == RecruiterSetupProfileStep.RSP1:
            self.fields["first_name"] = serializers.CharField()
            self.fields["last_name"] = serializers.CharField()
            self.fields["gender"] = serializers.CharField()
            self.fields["date_of_birth"] = serializers.DateField()
            self.fields["phone_number"] = serializers.CharField()
            self.fields["current_position"] = serializers.CharField()
            self.fields["cover_picture_id"] = serializers.CharField(required=False, allow_blank=True)
            self.fields["profile_picture_id"] = serializers.CharField(required=False, allow_blank=True)
        elif (
                step == RecruiterSetupProfileStep.RSP2
                or step == RecruiterSetupProfileStep.RSP3
        ):
            self.fields["company_profile"] = CompanySerializer(
                write_only=True, step=step
            )
        return super().to_internal_value(data)

    def create(self, validated_data):
        step = validated_data.pop("step", None)
        request = self.context.get("request", None)
        company = validated_data.pop("company_profile", None)
        user_id = request.user.pk if request and request.user else None
        company_instance = None
        instance = None
        validated_data["user_id"] = user_id
        validated_data["status"] = Status.PENDING
        validated_data["submitted_date"] = datetime.now()
        validated_data["request_type"] = RequestType.NEW_COMPANY
        validated_data["email"] = (
            request.user.email if request and request.user else None
        )
        validated_data["full_name"] = get_full_name(
            validated_data.get("first_name", None),
            validated_data.get("last_name", None),
        )
        _, user_company_profile_id = get_active_profile_id(request)
        user_company_profile = UserCompanyProfileService().get_by_id(
            user_company_profile_id
        )
        validated_data["profile_type"] = (
            user_company_profile.type
            if user_company_profile and user_company_profile.type
            else UserTypes.RECRUITER
        )
        existing_profile_id = getattr(user_company_profile, "profile_id", None)
        instance = None
        company_instance = None
        with transaction.atomic():
            if company:
                company["status"] = Status.PENDING
                company["is_active"] = False
                company_instance = CompanyService().create_as_profile(company)
                validated_data["company"] = company_instance
            if existing_profile_id:
                try:
                    instance = Profile.objects.get(pk=existing_profile_id)
                    update_fields = list(validated_data.keys())
                    for field, value in validated_data.items():
                        setattr(instance, field, value)
                    instance.save(update_fields=update_fields)
                except Profile.DoesNotExist:
                    # Fallback to create if link is broken
                    instance = super().create(validated_data)
            else:
                instance = super().create(validated_data)

            UserCompanyProfileService().update_profile_relation(
                company_id=instance.company_id if instance else None,
                profile_id=instance.id if instance else None,
                user_company_profile_id=user_company_profile_id,
            )
            UserService().update_fname_and_lname(user_id, validated_data)
            if step != RecruiterSetupProfileStep.RSP3:
                transaction.set_rollback(True)

        return instance


class RecruiterCompanyProfileSerializer(AlphanumericSerializer, BaseSerializer):
    alphanumeric_fields = [
        {
            "main": "city",
            "sub": "city_name",
            "main_format": PresentablePrimaryKeyRelatedField(
                queryset=GeoArea.objects.all(),
                presentation_serializer=GeoAreaInfoSerializer,
                required=False,
                allow_null=True,
            ),
        },
    ]
    city = serializers.CharField()
    name = serializers.CharField()
    industry = serializers.CharField()
    found_date = serializers.CharField()
    address = serializers.CharField()
    country = PresentablePrimaryKeyRelatedField(
        queryset=Country.objects.all(),
        presentation_serializer=CountryInfoSerializer,
    )
    phone_number = serializers.CharField()
    email = serializers.EmailField()

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "industry",
            "found_date",
            "company_size",
            "address",
            "city",
            "city_name",
            "country",
            "postal_code",
            "phone_number",
            "email",
            "website",
            "linkedin_email",
            "status",
            "about_me",
        ]

        extra_kwargs = {
            "id": {"read_only": True},
        }

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        data["cover_image_url"] = (presentation.get("cover_image") or {}).get("file_path")
        return data


class TelegramSignupSerializer(BaseSerializer):
    """
    Signup via phone number.
    """
    def __init__(self, instance=None, data=..., profile_type=None, **kwargs):
        self.profile_type = profile_type
        super().__init__(instance, data, **kwargs)

    class Meta:
        model = User
        fields = ["id", "phone_number", "password"]
        extra_kwargs = {
            "id": {"read_only": True},
            "password": {"write_only": True},
            "phone_number": {"required": True},
        }

    def validate_phone_number(self, value: str) -> str:
        value = value.strip()
        if not is_valid_phone_number(value):
            raise serializers.ValidationError({"phone_number": "Invalid phone number format."})
        exists = User.objects.filter(
            phone_number=value,
            status=UserStatus.ACTIVE,
            is_active=True,
        ).exclude(state=UserState.PENDING_VERIFY_OPT).exists()

        if exists:
            raise serializers.ValidationError("Unable to create the account.")
        return value


    def validate_password(self, password: str) -> str:
        user = self.instance or self.Meta.model()
        try:
            django_validate_password(password, user=user)
        except DjangoValidationError as e:
            logger.error(f"Password validation failed: {e}")
            raise serializers.ValidationError(list(e.messages))
        return password

    @transaction.atomic()
    def create(self, validated_data: dict):
        phone_number = validated_data.get("phone_number")
        encrypted_password = validated_data.get("password")

        try:
            password = EncryptionMixin().decrypt_value(encrypted_password)
        except Exception as e:
            logger.error(f"Unable to create the account: {e}")
            raise serializers.ValidationError(
                {"detail": "Unable to create the account."}
            )

        validated_data["username"] = phone_number # username = phone
        validated_data["phone_number"] = phone_number # username = phone
        validated_data["status"] = UserStatus.ACTIVE
        validated_data["is_active"] = True
        validated_data["state"] = UserState.PENDING_VERIFY_OPT
        validated_data["password"] = make_password(password)
        validated_data["login_type"] = "telegram"

        user = super().create(validated_data)

        # Deactivate duplicate pending accounts for the same phone
        dup_q = (
            Q(state=UserState.PENDING_VERIFY_OPT)
            & Q(username__iexact=phone_number)
        )
        User.objects.filter(dup_q).exclude(pk=user.pk).update(
            is_active=False,
            status=UserStatus.INACTIVE,
        )

        # Profile + role
        default_company = get_default_company()
        default_company_id = (
            default_company.pk
            if default_company and self.profile_type == UserTypes.APPLICANT
            else None
        )

        profile_data = {
            "user": user.pk,
            "status": ProfileStatus.ACTIVE,
            "type": self.profile_type,
            "state": UserState.PENDING_VERIFY_OPT,
            "company": default_company_id,
        }
        user_company_profile_instance = UserCompanyProfileService.create(profile_data)

        if self.profile_type == UserTypes.RECRUITER:
            default_role = get_default_role(code=DefaultRole.RECRUITER_ROLE)
        elif self.profile_type == UserTypes.ADMIN_RECRUITER:
            default_role = get_default_role(code=DefaultRole.PENDING_ADMIN_RECRUITER_ROLE)
        else:
            default_role = get_default_role(code=DefaultRole.APPLICANT_ROLE)

        user_company_profile_instance.roles.set(default_role)

        if not user.default_user_profile_company:
            user.default_user_profile_company = (
                user_company_profile_instance.pk
                if user_company_profile_instance
                else None
            )
            user.is_login = True
            user.save()

        return user