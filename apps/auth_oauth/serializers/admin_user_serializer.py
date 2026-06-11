from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.query_utils import Q
from django.utils import timezone
from drf_extra_fields.relations import PresentablePrimaryKeyRelatedField
from drf_writable_nested.serializers import WritableNestedModelSerializer
from rest_framework import serializers
from rest_framework.fields import CreateOnlyDefault

from apps.auth_oauth.constants.auth_constants import PermissionOptions, UserStatus, DefaultRole, GroupTypes
from apps.auth_oauth.constants.auth_constants import (
    ProfileStatus,
    ProfileCode,
    UserState,
    UserTypes,
)
from apps.auth_oauth.mixins.encryption_mixins import EncryptionMixin
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.models.permission_model import RolePermission, Permission
from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.models.role_model import Role
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.auth_oauth.serializers.auth_serializer import (
    UserLookUpSerializer,
    UserSerializer,
)
from apps.auth_oauth.serializers.role_serializer import RoleInfoSerializer
from apps.auth_oauth.services.send_email_service import EmailService
from apps.auth_oauth.services.user_company_profile_service import (
    UserCompanyProfileService,
)
from apps.auth_oauth.services.user_profile_service import UserProfileService
from apps.auth_oauth.services.user_service import UserService
from apps.base.constants.base_constants import Status
from apps.base.models.company_model import Company
from apps.base.serializers.base_serializer import BaseSerializer, BaseCompanySerializer, BaseAndAuditSerializer
from apps.base.serializers.company_serializer import (
    CompanyLookUpSerializer,
    RequestCompanyLookUpSerializer,
)
from apps.base.utils.base_util import get_default_company
from apps.base.utils.file_management_util import FileURLService
from apps.core.exceptions.base_exceptions import BadRequestException


encryption = EncryptionMixin()


STATUS_CHOICES = [("approved", "Approved"), ("rejected", "Reject")]
DISALLOWED_PERMISSION_GROUPS = {GroupTypes.OPERATOR, GroupTypes.ADMIN_RECRUITER, GroupTypes.APPLICANT}


class OperatorRoleListSerializer(BaseSerializer):
    type = serializers.ChoiceField(choices=UserTypes.choices)

    class Meta:
        model = Role
        fields = ["id", "name", "code", "type", "description"]


class OperatorAssignRolesSerializer(BaseSerializer):
    type = serializers.ChoiceField(choices=UserTypes.choices)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), write_only=True)
    company = PresentablePrimaryKeyRelatedField(
        queryset=Company.objects.all(),
        presentation_serializer=CompanyLookUpSerializer,
    )
    roles = serializers.ListField(
        child=serializers.IntegerField(required=True), required=True, write_only=True
    )
    profile_picture_id = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, write_only=True
    )
    cover_picture_id = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, write_only=True
    )

    class Meta:
        model = UserCompanyProfile
        fields = ["id", "company", "type", "roles", "user", "profile_picture_id", "cover_picture_id"]
        extra_kwargs = {
            "id": {"read_only": True},
        }

    def to_representation(self, instance):
        role_query = instance.roles.all()
        data = super().to_representation(instance)
        data["roles"] = RoleInfoSerializer(role_query, many=True).data
        return data

    def create(self, validated_data):
        validated_data["code"] = ProfileCode.OPERATOR
        validated_data["status"] = ProfileStatus.ACTIVE
        validated_data["state"] = UserState.COMPLETE_SETUP_PROFILE
        profile_picture_id = validated_data.pop("profile_picture_id", None)
        cover_picture_id = validated_data.pop("cover_picture_id", None)

        user = validated_data.get("user")
        company = validated_data.get("company")  # per-company profile
        ptype = validated_data.get("type")
        profile, created = Profile.objects.get_or_create(
            user=user,
            company=company,
            defaults={
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": f"{user.first_name} {user.last_name}".strip(),
                "profile_type": ptype,
                "status": Status.COMPLETE,
                "profile_picture_id": profile_picture_id,
                "cover_picture_id": cover_picture_id,
            },
        )
        if not created:
            # overwrite to keep in sync with required user fields
            profile.first_name = user.first_name
            profile.last_name = user.last_name
            profile.full_name = f"{user.first_name} {user.last_name}".strip()
            profile.profile_type = ptype
            profile.status = Status.COMPLETE
            profile.profile_picture_id = profile_picture_id
            profile.cover_picture_id = cover_picture_id
            profile.save(
                update_fields=["first_name", "last_name", "full_name", "profile_type", "status", "profile_picture_id",
                               "cover_picture_id", ])

        instance = self.get_object_instance(validated_data)
        if not instance:
            instance = super().create(validated_data)
        else:
            instance.roles.set(validated_data.get("roles", []))
        if instance.profile_id != profile.id:
            instance.profile = profile
            instance.save(update_fields=["profile"])
        return instance

    def get_object_instance(self, validated_data):
        user = validated_data.get("user")
        company = validated_data.get("company")
        type_ = validated_data.get("type")

        instance = UserCompanyProfile.objects.filter(
            type=type_,
            company=company,
            user=user,
        ).first()
        return instance


class RecruiterRequestCompanyAssignRolesSerializer(BaseSerializer):
    type = serializers.ChoiceField(choices=UserTypes.choices)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), write_only=True)
    company = PresentablePrimaryKeyRelatedField(
        queryset=Company.objects.all(),
        presentation_serializer=CompanyLookUpSerializer,
    )
    roles = serializers.ListField(
        child=serializers.IntegerField(required=True), required=True, write_only=True
    )

    class Meta:
        model = UserCompanyProfile
        fields = ["id", "company", "type", "roles", "user", ]
        extra_kwargs = {
            "id": {"read_only": True},
        }

    def to_representation(self, instance):
        role_query = instance.roles.all()
        instance = super().to_representation(instance)
        instance["roles"] = RoleInfoSerializer(role_query, many=True).data
        return instance

    def create(self, validated_data):
        validated_data["code"] = ProfileCode.REQUEST_NEW
        validated_data["status"] = ProfileStatus.ACTIVE
        validated_data["state"] = UserState.COMPLETE_SETUP_PROFILE
        existing_profile = self.context.get("profile_info")
        if not existing_profile:
            raise serializers.ValidationError("Existing profile is required to create a new new company.")
        user = validated_data.get("user")
        company = validated_data.get("company")  # per-company profile
        ptype = validated_data.get("type")
        defaults = {
            "first_name": existing_profile.first_name,
            "last_name": existing_profile.last_name,
            "full_name": existing_profile.full_name or f"{existing_profile.first_name} {existing_profile.last_name}".strip(),
            "gender": existing_profile.gender,
            "date_of_birth": existing_profile.date_of_birth,
            "phone_number": existing_profile.phone_number,
            "email": existing_profile.email,
            "location": existing_profile.location,
            "linkedin_profile": existing_profile.linkedin_profile,
            "website": existing_profile.website,
            "current_position": existing_profile.current_position,
            "about_me": existing_profile.about_me,
            "location_name": existing_profile.location_name,
            "department": existing_profile.department,
            "profile_type": ptype,
            "status": Status.PENDING,
            "profile_picture_id": existing_profile.profile_picture_id,
            "cover_picture_id": existing_profile.cover_picture_id,
            "submitted_date": timezone.now(),
            "request_type": "new_company"
        }

        profile, created = Profile.objects.get_or_create(
            user=user,
            company=company,
            defaults=defaults
        )
        if not created:
            if not created:
                # overwrite to keep in sync with required fields
                for field, value in defaults.items():
                    setattr(profile, field, value)
                profile.status = Status.COMPLETE
                profile.save(update_fields=list(defaults.keys()) + ["status"])
        instance = self.get_object_instance(validated_data)
        if not instance:
            instance = super().create(validated_data)
        else:
            instance.roles.set(validated_data.get("roles", []))
        if instance.profile_id != profile.id:
            instance.profile = profile
            instance.save(update_fields=["profile"])
        return instance

    def get_object_instance(self, validated_data):
        user = validated_data.get("user")
        company = validated_data.get("company")
        type_ = validated_data.get("type")

        instance = UserCompanyProfile.objects.filter(
            type=type_,
            company=company,
            user=user,
        ).first()
        return instance


class RolePermissionSerializer(BaseSerializer):
    perm_type = serializers.ChoiceField(required=True, choices=PermissionOptions)
    permission = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.exclude(group__in=DISALLOWED_PERMISSION_GROUPS))

    class Meta:
        model = RolePermission
        fields = ["id", "permission", "perm_type"]

class OperatorRolePermissionSerializer(BaseSerializer):
    perm_type = serializers.ChoiceField(required=True, choices=PermissionOptions)
    permission = serializers.PrimaryKeyRelatedField(queryset=Permission.objects.all())

    class Meta:
        model = RolePermission
        fields = ["id", "permission", "perm_type"]

class RoleSerializer(WritableNestedModelSerializer, BaseSerializer):
    type = serializers.ChoiceField(choices=UserTypes.choices)
    role_permissions = OperatorRolePermissionSerializer(many=True, required=False)
    company = BaseCompanySerializer(read_only=True)  # READ
    company_id = serializers.PrimaryKeyRelatedField(  # WRITE
        source="company", queryset=Company.objects.all(),
        required=False, allow_null=True,
        default=CreateOnlyDefault(get_default_company),
        write_only=True,
    )
    name = serializers.CharField(required=True, allow_null=False)
    is_public = serializers.BooleanField(default=True, required=False, allow_null=True)

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "code",
            "type",
            "company",
            "company_id",
            "active",
            "description",
            "own_only",
            "is_public",
            "role_permissions",
            "is_default",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "name": {"required": True},
        }

    def to_internal_value(self, data):
        default_company = get_default_company()
        data["company"] = default_company.id if default_company else None

        return super().to_internal_value(data)


class OperatorRequestDetailSerializer(serializers.ModelSerializer):
    company = PresentablePrimaryKeyRelatedField(
        queryset=Company.objects.all(),
        presentation_serializer=RequestCompanyLookUpSerializer,
    )

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
            "submitted_date",
            "profile_type",
            "company",
            "status",
            "request_type",
        ]
        
    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        
        return data


class OperatorCurrentUserSerializer(UserSerializer):
    pass


class OperatorSendInviteSerializer(serializers.Serializer):
    pass


class OperatorApprovalSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    reason = serializers.CharField(
        source="approval_reason", required=False, allow_null=True, allow_blank=True
    )

    def to_internal_value(self, data):
        if data.get("status", None) == Status.REJECTED:
            self.fields["reason"] = serializers.CharField(source="approval_reason")
        return super().to_internal_value(data)

    def validate(self, attrs):
        if self.instance.status != Status.PENDING:
            raise BadRequestException(f"Record has been {self.instance.status}")
        return super().validate(attrs)


class OperatorAllRequestSerializer(BaseSerializer):
    user = PresentablePrimaryKeyRelatedField(
        queryset=User.objects.all(),
        presentation_serializer=UserLookUpSerializer,
    )
    company = PresentablePrimaryKeyRelatedField(
        queryset=Company.objects.all(),
        presentation_serializer=CompanyLookUpSerializer,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context["include_cover"] = False

    class Meta:
        model = Profile
        fields = [
            "id",
            "status",
            "submitted_date",
            "user",
            "company",
            "profile_type",
            "request_type",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        presentation = FileURLService.present_profile_images(instance)
        data["profile_image_url"] = (presentation.get("profile_image") or {}).get("file_path")
        return data


class CompanyInputSerializer(serializers.Serializer):
    company_id = serializers.IntegerField()
    is_default = serializers.BooleanField(required=False, default=True)
    roles = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, allow_empty=True
    )

    def to_internal_value(self, data):
        data = dict(data)
        roles = data.get("roles")

        if not roles:
            default_id = (
                Role.objects.filter(code=DefaultRole.ADMIN_RECRUITER_ROLE)
                .values_list("id", flat=True)
                .first()
            )
            if not default_id:
                raise ValidationError({"roles": "Default recruiter role is not configured"})
            data["roles"] = [default_id]

        return super().to_internal_value(data)


class AdminUserSerializer(WritableNestedModelSerializer, BaseSerializer):
    last_name = serializers.CharField()
    first_name = serializers.CharField()
    email = serializers.EmailField()
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    types = serializers.SerializerMethodField()
    companies = CompanyInputSerializer(many=True, write_only=True, required=True)
    
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "password",
            "full_name",
            "types",
            "companies",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "password": {"write_only": True},
        }

    def validate_companies(self, companies):
        if not companies:
            raise serializers.ValidationError("Please include at least one company.")

        exclude_user_id = getattr(self.instance, "pk", None)

        company_ids = {item["company_id"] for item in companies}
        conflicts = (
            UserCompanyProfile.objects
            .filter(company_id__in=company_ids)
            .filter(
                Q(type=UserTypes.ADMIN_RECRUITER.value) |
                Q(roles__type=UserTypes.ADMIN_RECRUITER.value)
            )
            .exclude(user__status=UserStatus.DELETED)
            .exclude(user_id=exclude_user_id)
            .values_list("company_id", flat=True)
            .distinct()
        )
        if conflicts:
            raise serializers.ValidationError("A company already have ADMIN RECRUITER.")
        return companies

    def get_types(self, instance):
        user_company_profiles = UserCompanyProfileService().get_all_by_user_id(instance.id)
        return [p.type for p in user_company_profiles if p.type]

    def to_internal_value(self, data):
        request = self.context.get("request", None)
        password = data.get("password") or ""
        data["password"] = password

        if request and request.method == "PUT":
            self.fields["password"] = serializers.CharField(
                required=False, allow_null=True, allow_blank=True, write_only=True
            )
        return super().to_internal_value(data)

    def validate(self, attrs):
        username = attrs.get("username")
        email = attrs.get("email")
        exclude_id = getattr(self.instance, "pk", None)
        UserService().validate_user(username, email, exclude_id=exclude_id)
        return super().validate(attrs)

    @transaction.atomic()
    def create(self, validated_data):
        encrypted_password = validated_data.pop("password", None)
        companies = validated_data.pop("companies", [])
        decrypted_password = ""
            
        if encrypted_password:
            decrypted_password = encryption.decrypt_value(encrypted_password)
            validated_data["password"] = make_password(decrypted_password)
            validated_data["is_required_reset_pwd"] = True
            validated_data["default_password"] = encryption.encrypt_value(decrypted_password)
            
        validated_data["state"] = UserState.PENDING_VERIFY_OPT

        instance = super().create(validated_data)

        dup_q = (
                Q(state=UserState.PENDING_VERIFY_OPT) &
                (Q(username__iexact=instance.username) & Q(email__iexact=instance.email))
        )
        affected = (
            User.objects
            .filter(dup_q)
            .exclude(pk=instance.pk)
            .update(
                is_active=False,
                status=UserStatus.INACTIVE,
            )
        )
        default_company_profile = None
        for company_data in companies:
            company_id = company_data.get("company_id")
            is_default = company_data.get("is_default", False)
            roles = company_data.get("roles", [])

            user_company_payload = {
                "user": instance.pk,
                "company": company_id,
                "type": UserTypes.ADMIN_RECRUITER.value,
                "roles": roles,
            }
            operator_serializer = OperatorAssignRolesSerializer(data=user_company_payload, context=self.context)
            operator_serializer.is_valid(raise_exception=True)
            user_company_profile = operator_serializer.save()
            if is_default:
                default_company_profile = user_company_profile

        if default_company_profile:
            instance.default_user_profile_company = default_company_profile.pk
            instance.is_login = True
            instance.save()

        template_context = EmailService().template_context(user=instance, default_password=decrypted_password)
        EmailService().send_invite(instance, template_context)

        return instance

    @transaction.atomic()
    def update(self, instance, validated_data):
        encrypted_password = validated_data.pop("password", None)
        companies = validated_data.pop("companies", None)
        
        if encrypted_password:
            decrypted_password = encryption.decrypt_value(encrypted_password)
            validated_data["password"] = make_password(decrypted_password)
            validated_data["default_password"] = encryption.encrypt_value(decrypted_password)
            
        user_company_profile = UserCompanyProfileService().get_by_code(
            user_id=instance.pk, code=ProfileCode.OPERATOR
        )
        profile_data = {
            "user": instance.pk,
            "first_name": validated_data.get("first_name"),
            "last_name": validated_data.get("last_name"),
            "date_of_birth": validated_data.get("date_of_birth"),
            "status": Status.COMPLETE,
        }
        profile_instance = user_company_profile.profile if user_company_profile else None
        profile = UserProfileService.update(profile_instance, profile_data)
        # handle companies
        default_ucp = None
        if companies is not None:
            for company_data in companies:
                company_id = company_data.get("company_id")
                is_default = company_data.get("is_default", False)
                roles = company_data.get("roles", [])

                user_company_payload = {
                    "user": instance.pk,
                    "company": company_id,
                    "type": UserTypes.ADMIN_RECRUITER.value,
                    "roles": roles,
                }

                operator_serializer = OperatorAssignRolesSerializer(
                    data=user_company_payload,
                    context=self.context,
                )
                operator_serializer.is_valid(raise_exception=True)
                ucp = operator_serializer.save()

                if is_default:
                    default_ucp = ucp

        if default_ucp:
            instance.default_user_profile_company = default_ucp.pk
            instance.save(update_fields=["default_user_profile_company"])
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user_company_profiles = UserCompanyProfileService().get_all_by_user_id(instance.id)
        new_context = self.context.copy()
        new_context["include_cover"] = False
        data["companies"] = OperatorAssignRolesSerializer(
            user_company_profiles,
            many=True,
            context=new_context,
        ).data
        profiles = getattr(instance, "profiles_prefetched", [])
        data["profile_image_url"] = None

        if profiles:
            presentation = FileURLService.present_profile_images(profiles[0])
            data["profile_image_url"] = (
                presentation.get("profile_image") or {}
            ).get("file_path")

        return data

