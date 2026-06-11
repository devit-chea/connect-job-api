from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.query_utils import Q
from drf_writable_nested.serializers import WritableNestedModelSerializer
from rest_framework import serializers

from apps.auth_oauth.constants.auth_constants import (
    DefaultRole,
    ProfileCode,
    ProfileStatus,
    UserState,
    UserStatus,
    UserTypes,
)
from apps.auth_oauth.mixins.encryption_mixins import EncryptionMixin
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.models.role_model import Role
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.auth_oauth.serializers.admin_user_serializer import RolePermissionSerializer
from apps.auth_oauth.serializers.role_serializer import RoleInfoSerializer
from apps.auth_oauth.services.send_email_service import EmailService
from apps.auth_oauth.services.user_company_profile_service import (
    UserCompanyProfileService,
)
from apps.auth_oauth.services.user_service import UserService
from apps.base.constants.base_constants import Status
from apps.base.models.company_model import Company
from apps.base.serializers.base_serializer import (
    BaseSerializer,
    BaseCompanySerializer,
    BaseAndAuditSerializer,
)
from apps.base.utils.file_management_util import FileURLService

encryption = EncryptionMixin()


class UserInfoSerializer(BaseSerializer):
    full_name = serializers.CharField(source="get_full_name")
    profile_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "full_name", "profile_url"]
        ref_name = "recruiter_user_info"

    def get_profile_url(self, obj):
        return "tmp_url"


class CompanyInfoSerializer(BaseSerializer):
    profile_url = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = ["id", "name", "profile_url"]

    def get_profile_url(self, obj):
        return "tmp_url"


class CompanyDetailInfoSerializer(BaseSerializer):
    profile_url = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "profile_url",
            "industry",
            "found_date",
            "address",
            "city",
            "country",
            "postal_code",
            "phone_number",
            "email",
            "linkedin_email",
            "website",
        ]

    def get_profile_url(self, obj):
        return "tmp_url"


class RecruiterAdminCreateUserSerializer(WritableNestedModelSerializer, BaseSerializer):
    last_name = serializers.CharField()
    first_name = serializers.CharField()
    email = serializers.EmailField()
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    type = serializers.ChoiceField(choices=UserTypes.choices, write_only=True)
    roles = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text="List of role IDs for this user within the company",
    )

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "full_name",
            "last_name",
            "email",
            "username",
            "password",
            "type",
            "roles",
            "is_active",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "password": {"write_only": True},
        }

    def validate(self, attrs):
        username = attrs.get("username")
        email = attrs.get("email")
        exclude_id = getattr(self.instance, "pk", None)
        UserService().validate_user(username, email, exclude_id=exclude_id)
        request = self.context.get("request")
        company_id = getattr(request, "company_id", None)
        if not company_id:
            raise ValidationError("company not found")

        role_ids = list(set(attrs.get("roles") or []))
        if role_ids:
            found = set(
                Role.objects.filter(pk__in=role_ids, company_id=company_id).values_list(
                    "id", flat=True
                )
            )
            if len(found) != len(role_ids):
                raise ValidationError({"roles": "Role(s) not found for your company"})
        else:
            default_id = (
                Role.objects.filter(code=DefaultRole.RECRUITER_ROLE)
                .values_list("id", flat=True)
                .first()
            )
            if not default_id:
                raise ValidationError(
                    {"roles": "Default recruiter role is not configured"}
                )
            found = {default_id}
        attrs.update(
            {
                "_company_id": company_id,
                "_roles": list(found),
                "type": UserTypes.RECRUITER.value,
            }
        )

        return super().validate(attrs)

    def to_internal_value(self, data):
        request = self.context.get("request", None)
        password = data.get("password") or ""
        data["password"] = password
        if request and request.method == "PUT":
            self.fields["password"] = serializers.CharField(
                required=False, allow_null=True, allow_blank=True, write_only=True
            )
        return super().to_internal_value(data)

    def get_types(self, instance):
        user_company_profiles = UserCompanyProfileService().get_all_by_user_id(
            instance.id
        )
        types = [p.type for p in user_company_profiles if p.type]
        return "/".join(types) if types else "N/A"

    def _ensure_profile(self, user, ptype, company_id: int | None):
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.first_name = user.first_name
        profile.last_name = user.last_name
        profile.profile_type = ptype
        profile.full_name = f"{(user.first_name or '').strip()} {(user.last_name or '').strip()}".strip()
        profile.status = Status.COMPLETE
        profile.company = Company.objects.get(pk=company_id)
        profile.email = user.email
        profile.save(
            update_fields=[
                "first_name",
                "last_name",
                "full_name",
                "profile_type",
                "status",
                "company",
                "email",
            ]
        )
        return profile

    @transaction.atomic()
    def create(self, validated_data):
        encrypted_password = validated_data.get("password")

        if encrypted_password:
            decrypted_password = encryption.decrypt_value(encrypted_password)
            validated_data["password"] = make_password(decrypted_password)
            validated_data["is_required_reset_pwd"] = True
            validated_data["default_password"] = make_password(decrypted_password)
        validated_data["state"] = UserState.PENDING_VERIFY_OPT

        company_id = validated_data.pop("_company_id")
        role_ids = validated_data.pop("_roles")
        ptype_value = validated_data.pop("type")
        validated_data.pop("roles", None)
        user = super().create(validated_data)

        dup_q = Q(state=UserState.PENDING_VERIFY_OPT) & (
            Q(username__iexact=user.username) & Q(email__iexact=user.email)
        )
        affected = (
            User.objects.filter(dup_q)
            .exclude(pk=user.pk)
            .update(
                is_active=False,
                status=UserStatus.INACTIVE,
            )
        )

        profile = self._ensure_profile(user, ptype=ptype_value, company_id=company_id)

        ucp_payload = {
            "user": user.pk,
            "status": ProfileStatus.ACTIVE,
            "type": ptype_value,
            "company": company_id,
            "code": ProfileCode.ADMIN_RECRUITER,
            "state": UserState.COMPLETE_SETUP_PROFILE,
            "profile": profile.pk,
        }
        user_company_profile_instance = UserCompanyProfileService.create(ucp_payload)
        if user_company_profile_instance and hasattr(
            user_company_profile_instance, "roles"
        ):
            user_company_profile_instance.roles.set(role_ids)

        if not user.default_user_profile_company:
            user.default_user_profile_company = (
                user_company_profile_instance.pk
                if user_company_profile_instance
                else None
            )
            user.is_login = True
            user.save(update_fields=["default_user_profile_company", "is_login"])

        template_context = EmailService().template_context(
            user=user, default_password=decrypted_password
        )
        EmailService().send_invite(user, template_context)
        return user

    @transaction.atomic()
    def update(self, instance, validated_data):
        company_id = validated_data.pop("_company_id")
        role_ids = validated_data.pop("_roles", None)
        ptype_value = validated_data.pop("type", None)

        validated_data.pop("roles", None)
        validated_data.pop("type", None)

        encrypted_password = validated_data.get("password")
        if encrypted_password:
            decrypted_password = encryption.decrypt_value(encrypted_password)
            validated_data["password"] = make_password(decrypted_password)
            validated_data["is_required_reset_pwd"] = True
            validated_data["default_password"] = encryption.encrypt_value(
                decrypted_password
            )
        else:
            validated_data.pop("password", None)
        user = super().update(instance, validated_data)

        profile = self._ensure_profile(user, ptype_value or None, company_id)

        ucp = UserCompanyProfileService.get_by_user_and_company(user.id, company_id)
        if not ucp:
            ucp_payload = {
                "user": user.pk,
                "status": ProfileStatus.ACTIVE,
                "type": ptype_value or getattr(profile, "profile_type", None),
                "company": company_id,
                "code": ProfileCode.ADMIN_RECRUITER,
                "state": UserState.COMPLETE_SETUP_PROFILE,
                "profile": profile.pk,
            }
            ucp = UserCompanyProfileService.create(ucp_payload)
        else:
            if ucp.profile_id != profile.pk:
                ucp.profile_id = profile.pk
            if ptype_value is not None:
                ucp.type = ptype_value
                profile.profile_type = ptype_value
                profile.save(update_fields=["profile_type"])
            ucp.save(
                update_fields=(
                    ["profile_id", "type"]
                    if ptype_value is not None
                    else ["profile_id"]
                )
            )
        if role_ids is not None:
            if hasattr(ucp, "roles"):
                ucp.roles.set(role_ids)
            elif hasattr(ucp, "role_id"):
                ucp.role_id = role_ids[0] if role_ids else None
                ucp.save(update_fields=["role_id"])
        if not user.default_user_profile_company:
            user.default_user_profile_company = ucp.pk
            user.save(update_fields=["default_user_profile_company"])
        setattr(user, "active_recruiter_ucps", [ucp])
        return user

    def to_representation(self, instance):
        data = super().to_representation(instance)
        view = self.context.get("view")
        is_detail = getattr(view, "action", None) == "retrieve"

        ucp = None
        if (
            hasattr(instance, "active_recruiter_ucps")
            and instance.active_recruiter_ucps
        ):
            ucp = instance.active_recruiter_ucps[0]
        if not ucp:
            ucp = UserCompanyProfileService.get_by_id(
                instance.default_user_profile_company
            )

        if not ucp:
            request = self.context.get("request")
            company_id = getattr(request, "company_id", None)
            if company_id:
                ucp = (
                    UserCompanyProfile.objects.select_related("company", "profile")
                    .prefetch_related("roles")
                    .filter(user_id=instance.id, company_id=company_id)
                    .order_by("-id")
                    .first()
                )
        if ucp:
            data["type"] = getattr(ucp, "type", None)
            if hasattr(ucp, "roles"):
                roles_qs = ucp.roles.all()
                if is_detail:
                    roles_qs = roles_qs.exclude(code=DefaultRole.RECRUITER_ROLE)
                data["roles"] = RoleInfoSerializer(roles_qs, many=True).data
            else:
                data["roles"] = []

            data["user_status"] = getattr(instance, "status", None)
            data["user_state"] = getattr(instance, "state", None)
            data["user_profile_state"] = getattr(ucp, "state", None)
            prof = getattr(ucp, "profile", None)
            # fetch url via  file_id
            presentation = FileURLService.present_profile_images(prof)
            data["profile_image_url"] = (presentation.get("profile_image") or {}).get(
                "file_path"
            )
            data["cover_image_url"] = (presentation.get("cover_image") or {}).get(
                "file_path"
            )
            c = getattr(ucp, "company", None)
            company_presentation = FileURLService.present_profile_images(c)
            data["company"] = {
                "id": getattr(c, "id", None),
                "name": getattr(c, "name", None),
                "email": getattr(c, "email", None),
                "industry": getattr(c, "industry", None),
                "profile_picture_id": getattr(c, "profile_picture_id", None),
                "profile_image_url": (company_presentation.get("profile_image") or {}).get("file_path")
            }
            data["user_profile_id"] = getattr(ucp, "id", None)
        else:
            data.update(
                {
                    "type": None,
                    "roles": [],
                    "user_status": getattr(instance, "status", None),
                    "user_profile_status": None,
                    "user_state": getattr(instance, "state", None),
                    "user_profile_state": None,
                    "company": None,
                    "user_profile_id": None,
                    "company_id": None,
                    "profile_image_url": None,
                    "cover_image_url": None,
                }
            )

        return data


class AdminRecruiterRoleSerializer(
    WritableNestedModelSerializer, BaseAndAuditSerializer
):
    type = serializers.ChoiceField(choices=UserTypes.choices)
    role_permissions = RolePermissionSerializer(many=True, required=True)
    company = BaseCompanySerializer(read_only=True)
    name = serializers.CharField()

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "code",
            "type",
            "company",
            "active",
            "description",
            "role_permissions",
            "own_only",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "name": {"required": True},
        }
