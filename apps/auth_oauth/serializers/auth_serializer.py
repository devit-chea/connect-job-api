from datetime import datetime
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone
from django_rest_passwordreset.models import (
    ResetPasswordToken,
    clear_expired,
    get_password_reset_token_expiry_time,
    get_password_reset_lookup_field,
)
from django_rest_passwordreset.serializers import EmailSerializer
from django_rest_passwordreset.signals import reset_password_token_created
from django_rest_passwordreset.views import (
    ResetPasswordRequestToken,
    _unicode_ci_compare,
)
from drf_extra_fields.relations import PresentablePrimaryKeyRelatedField
from rest_framework import serializers
from rest_framework import status as http_status
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from apps.auth_oauth.constants.auth_constants import DefaultRole
from apps.auth_oauth.constants.auth_constants import (
    UserTypes,
    ProfileStatus,
    PermissionOptions,
)
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.models.permission_model import Permission, RolePermission
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.auth_oauth.services.user_company_profile_service import (
    UserCompanyProfileService,
)
from apps.auth_oauth.utils.auth_util import get_default_role
from apps.auth_setting.utils import setting_util
from apps.base.fields.base64_field import Base64ImageField
from apps.base.models.file_model import FileModel
from apps.base.serializers.base_serializer import BaseSerializer
from apps.base.utils.base64image_util import Base64ImageUtil
from apps.base.utils.base_util import get_default_company, is_valid_phone_number
from apps.base.utils.file_management_util import FileURLService
from apps.base.views.sys_setting_view import SysSettingViewByName
from apps.core.exceptions.base_exceptions import BadRequestException
from apps.auth_oauth.models.profile_model import Profile
from rest_framework.exceptions import PermissionDenied


class LoginForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].required = True
        self.fields["password"].required = True

    password = forms.CharField(required=False)
    username = forms.CharField(required=False)


class UserFileSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    file_name = serializers.CharField(read_only=True)
    file_url = serializers.SerializerMethodField()
    image_thumbnail_url = serializers.SerializerMethodField()

    def get_file_url(self, obj):
        return obj.file.url

    def get_image_thumbnail_url(self, obj):
        return obj.image_thumbnail.url


class UserListSerializer(BaseSerializer):
    is_send_email = serializers.BooleanField(
        style={"input_type": "send email reset"}, default=False
    )
    file = serializers.SerializerMethodField(read_only=True)
    full_name = serializers.CharField(
        source="get_full_name", required=False, read_only=True
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "login_type",
            "status",
            "base_company",
            "company",
            "is_send_email",
            "is_active",
            "groups",
            "file",
            "last_login",
            "is_password_lock",
            "is_password_expired",
            "is_two_step_verification",
            "is_disable",
            "full_name",
        ]
        extra_kwargs = {
            "email": {"required": True},
            "first_name": {"required": True},
            "last_name": {"required": True},
            "login_type": {"required": True},
            "company": {"write_only": True},
            "last_login": {"read_only": True},
            "base_company": {"write_only": True},
            "groups": {"write_only": True, "required": True},
            "id": {"read_only": True},
            "status": {"read_only": True},
        }

    def get_file(self, obj):
        file = FileModel.objects.filter(ref_id=obj.id, ref_type="user_profile").first()
        data = None
        if file:
            serializer = UserFileSerializer(file)
            data = serializer.data
        return data


class UserSerializer(BaseSerializer):
    is_send_email = serializers.BooleanField(
        style={"input_type": "send email reset"}, default=False
    )
    file = Base64ImageField(
        required=False,
        allow_empty_file=True,
        allow_null=True,
        write_only=True,
        default="",
    )
    full_name = serializers.CharField(
        source="get_full_name", required=False, read_only=True
    )
    is_set_up_profile = serializers.BooleanField(
        source="get_is_set_up_profile", read_only=True
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "login_type",
            "status",
            "base_company",
            "company",
            "is_send_email",
            "is_active",
            "groups",
            "file",
            "last_login",
            "password_expired",
            "is_password_lock",
            "is_password_expired",
            "is_disable",
            "full_name",
            "is_two_step_verification",
            "state",
            "is_set_up_profile",
        ]
        extra_kwargs = {
            "email": {"required": True},
            "first_name": {"required": True},
            "last_name": {"required": True},
            "last_login": {"read_only": True},
            "id": {"read_only": True},
            "status": {"read_only": True},
            "password_expired": {"read_only": True},
        }

    def create(self, validated_data, *args, **kwargs):
        with transaction.atomic():
            try:
                default_password = SysSettingViewByName.get_setting(
                    self, "DEFAULT_PASSWORD", validated_data["base_company"]
                )
                pass_expire_minute = SysSettingViewByName.get_setting(
                    self, "PASSWORD_EXPIRE_MINUTES", validated_data["base_company"]
                )

                user = User(
                    username=validated_data["username"],
                    email=validated_data["email"],
                    first_name=validated_data["first_name"],
                    last_name=validated_data["last_name"],
                    login_type=validated_data["login_type"],
                    base_company=validated_data["base_company"],
                    is_active=validated_data["is_active"],
                    is_two_step_verification=validated_data["is_two_step_verification"],
                    password_expired=datetime.now()
                                     + timedelta(minutes=int(pass_expire_minute)),
                )
                user.set_password(default_password)
                user.is_send_email = validated_data["is_send_email"]
                user.save()
                user.company.set(validated_data["company"])
                user.groups.set(validated_data["groups"])

                # *** Toggle Auth TOPT MAIL
                setting_util.toggle_auth_totp_mail(self.context.get("request"), user)

                if validated_data["file"]:
                    ref_id = user.pk
                    ref_type = "user_profile"
                    Base64ImageUtil.create_base64image(
                        validated_data["file"], ref_id, ref_type
                    )
            except Exception as e:
                transaction.set_rollback(True)
                raise serializers.ValidationError(detail=e)
        try:
            if user.email and validated_data["is_send_email"] == True:
                ResetPasswordRequestTokenInherit.post(
                    self, request=validated_data["email"]
                )
        except Exception as e:
            print(e)
        return user


class UserInfoSerializer(BaseSerializer):
    full_name = serializers.CharField(
        source="get_full_name", required=False, read_only=True
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
        ]
        ref_name = "user_info"

    def create(self, validated_data, *args, **kwargs):
        with transaction.atomic():
            try:
                default_password = SysSettingViewByName.get_setting(
                    self, "DEFAULT_PASSWORD", validated_data["base_company"]
                )
                pass_expire_minute = SysSettingViewByName.get_setting(
                    self, "PASSWORD_EXPIRE_MINUTES", validated_data["base_company"]
                )

                user = User(
                    username=validated_data["username"],
                    email=validated_data["email"],
                    first_name=validated_data["first_name"],
                    last_name=validated_data["last_name"],
                    login_type=validated_data["login_type"],
                    base_company=validated_data["base_company"],
                    is_active=validated_data["is_active"],
                    password_expired=datetime.now()
                                     + timedelta(minutes=int(pass_expire_minute)),
                )
                user.set_password(default_password)
                user.is_send_email = validated_data["is_send_email"]
                user.save()
                user.company.set(validated_data["company"])
                user.groups.set(validated_data["groups"])
                if validated_data["file"]:
                    ref_id = user.pk
                    ref_type = "user_profile"
                    Base64ImageUtil.create_base64image(
                        validated_data["file"], ref_id, ref_type
                    )
            except Exception as e:
                transaction.set_rollback(True)
                raise serializers.ValidationError(detail=e)
        try:
            if user.email and validated_data["is_send_email"] == True:
                ResetPasswordRequestTokenInherit.post(
                    self, request=validated_data["email"]
                )
        except Exception as e:
            print(e)
        return user


class LoginSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "username",
            "password",
        ]
        extra_kwargs = {"username": {"required": True}, "password": {"required": True}}

class TelegramResetPasswordSerializer(serializers.Serializer):
    phone_number = serializers.CharField()

    def validate_phone_number(self, value: str) -> str:
        value = value.strip()
        if not is_valid_phone_number(value):
            raise serializers.ValidationError("Invalid phone number format.")
        return value

class ResetPasswordRequestTokenInherit(ResetPasswordRequestToken):
    """
    An Api View which provides a method to request a password reset token based on an e-mail address

    Sends a signal reset_password_token_created when a reset token was created
    """

    throttle_classes = ()
    permission_classes = ()
    serializer_class = EmailSerializer
    authentication_classes = ()

    def post(self, request, status=None):
        # pass
        email = request
        # before we continue, delete all existing expired tokens
        password_reset_token_validation_time = get_password_reset_token_expiry_time()
        # datetime.now minus expiry hours
        now_minus_expiry_time = timezone.now() - timedelta(
            hours=password_reset_token_validation_time
        )
        invalid_data = {"form_errors": {}, "errors": {}}
        exception = {"error": invalid_data}
        # delete all tokens where create_date < now - 24 hours
        clear_expired(now_minus_expiry_time)
        # find a user by email address (case insensitive search)
        users = User.objects.filter(
            **{"{}__iexact".format(get_password_reset_lookup_field()): email}
        )

        # last but not least: iterate over all users that are active and can change their password
        # and create a Reset Password Token and send a signal with the created token
        for user in users:
            if user.is_lock and user.is_password_lock:
                invalid_data["form_errors"] = {"message": ["User Have been Locked"]}
                return Response(data=exception, status=http_status.HTTP_400_BAD_REQUEST)

            if _unicode_ci_compare(
                    email, getattr(user, get_password_reset_lookup_field())
            ):
                # define the token as none for now
                token = None
                # check if the user already has a token
                if user.password_reset_tokens.all().count() > 0:
                    # yes, already has a token, re-use this token
                    token = user.password_reset_tokens.all()[0]
                else:
                    # no token exists, generate a new token
                    token = ResetPasswordToken.objects.create(user=user)
                # send a signal that the password token was created
                # let whoever receives this signal handle sending the email for the password reset
                if user.is_active:
                    reset_password_token_created.send(
                        sender=self.__class__,
                        instance=self,
                        reset_password_token=token,
                        request=request,
                    )
        # done
        return token


class ChangePasswordSerializer(serializers.ModelSerializer):
    old_password = serializers.CharField(
        style={"input_type": "current new password"}, write_only=True
    )
    new_password1 = serializers.CharField(
        style={"input_type": "new password"}, write_only=True
    )
    new_password2 = serializers.CharField(
        style={"input_type": "confirm password"}, write_only=True
    )

    class Meta:
        model = User
        fields = [
            "old_password",
            "new_password1",
            "new_password2",
        ]


class UserLookUpSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
        ]


class RefreshTokenSerializer(TokenRefreshSerializer):
    refresh = serializers.CharField(required=False, help_text="WIll override cookie.")

    def get_refresh_token(self):
        request = self.context["request"]
        if "refresh" in request.data and request.data["refresh"] != "":
            return request.data["refresh"]
        cookie_name = settings.SIMPLE_JWT["REFRESH_COOKIE"]
        if cookie_name and cookie_name in request.COOKIES:
            return request.COOKIES.get(cookie_name)
        else:
            raise TokenError("Invalid credentials.")

    def validate(self, validated_data):
        validated_data["refresh"] = self.get_refresh_token()
        validated_data = super().validate(validated_data)
        if "refresh" not in validated_data:
            validated_data["refresh"] = self.get_refresh_token()

        return validated_data


class OperatorUserCreateSerializer(BaseSerializer):
    confirm_password = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "password",
            "confirm_password",
            "email",
            "first_name",
            "last_name",
        ]

    def create(self, validated_data):
        confirm_password = validated_data.pop("confirm_password")
        password = validated_data.get("password")
        if password != confirm_password:
            raise BadRequestException("password not match.")
        validated_data["password"] = make_password(password)
        instance = super().create(validated_data)
        default_company = get_default_company()
        default_company_id = default_company.pk if default_company else None
        data = {
            "user": instance.pk,
            "status": ProfileStatus.ACTIVE,
            "type": UserTypes.OPERATOR.value,
            "company": default_company_id,
        }

        user_company_profile_instance = UserCompanyProfileService.create(data)
        if not instance.default_user_profile_company:
            instance.default_user_profile_company = (
                user_company_profile_instance.pk
                if user_company_profile_instance
                else None
            )
            instance.is_login = True
            instance.save()
        # set default roles to operator

        default_operator_role = get_default_role(code=DefaultRole.OPERATOR_DEFAULT_ROLE)
        user_company_profile_instance.roles.set(default_operator_role)
        return instance


class ApplicantUserUpdateSerializer(BaseSerializer):
    file = Base64ImageField(
        max_length=None,
        required=False,
        allow_empty_file=True,
        allow_null=True,
        write_only=True,
        default="",
    )
    password = serializers.CharField(required=False, write_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "password",
            "email",
            "first_name",
            "last_name",
            "file",
        ]


class ResetPasswordForgotPasswordSerializer(serializers.Serializer):
    password = serializers.CharField()
    password_confirm = serializers.CharField()
    reset_token = serializers.CharField(write_only=True)

class ResetPasswordChangePasswordSerializer(serializers.Serializer):
    password = serializers.CharField()
    password_confirm = serializers.CharField()

class EnabledUserSerializer(serializers.Serializer):
    pass


class DisabledUserSerializer(serializers.Serializer):
    pass


class ProfileSerializer(serializers.ModelSerializer):
    from apps.base.serializers.company_serializer import CompanyLookUpSerializer
    from apps.base.models.company_model import Company

    name = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    company = PresentablePrimaryKeyRelatedField(
        queryset=Company.objects.all(),
        presentation_serializer=CompanyLookUpSerializer,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = UserCompanyProfile
        fields = ["id", "phone", "name", "email", "type", "company", "state"]

    def get_name(self, instance):
        first_name = self.safe_get(instance.profile, "first_name")
        last_name = self.safe_get(instance.profile, "last_name")
        full_name = "%s %s" % (first_name, last_name)
        return full_name.strip()

    def get_phone(self, instance):
        return self.get_value_type_base(instance, "phone_number")

    def get_email(self, instance):
        return self.get_value_type_base(instance, "email")

    def safe_get(self, attr, key):
        return getattr(attr, key, None) if attr else None

    def get_value_type_base(self, instance, key):
        value = None

        if instance.type == UserTypes.APPLICANT.value:
            value = self.safe_get(instance.profile, key)
        elif (
                instance.type == UserTypes.RECRUITER
                or instance.type == UserTypes.ADMIN_RECRUITER
        ):
            value = self.safe_get(instance.company, key)
        elif instance.type == UserTypes.OPERATOR:
            value = None

        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["profile_id"] = getattr(instance.profile, 'pk', None)
        data["profile_picture_id"] = getattr(instance.profile, 'profile_picture_id', None)
        presentation = FileURLService.present_profile_images(instance.profile)
        data["profile_image_url"] =  (presentation.get("profile_image") or {}).get("file_path")
        data["cover_image_url"] =  (presentation.get("cover_image") or {}).get("file_path")
        return data


class CurrentUserSerializer(BaseSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    current_profile = serializers.SerializerMethodField()
    profiles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "last_login",
            "password_expired",
            "full_name",
            "is_required_reset_pwd",
            "current_profile",
            "profiles",
            "login_type",
        ]

    def get_current_profile(self, instance):
        """
        IMPORTANT SECURITY FIX:
        Validate that the selected profile belongs to the authenticated user.
        Never trust user_agent blindly.
        """

        user_agent = self.context.get("user_agent")
        user_company_profile_id = (
            user_agent.get("user_company_profile_id") if user_agent else None
        )

        if not user_company_profile_id:
            raise PermissionDenied("Access denied.")

        # STRICT: profile must belong to this user
        current_profile = (
            instance.user_company_profile_user
            .filter(id=user_company_profile_id, status=ProfileStatus.ACTIVE)
            .first()
        )

        if not current_profile:
            # General, not leaking info
            raise PermissionDenied("You are not authorized to access this profile.")

        return ProfileSerializer(current_profile).data

    def get_profiles(self, instance):
        """
        Return all other profiles the user owns.
        """
        user_agent = self.context.get("user_agent")
        user_company_profile_id = (
            user_agent.get("user_company_profile_id") if user_agent else None
        )

        profiles = instance.user_company_profile_user.filter(
            status=ProfileStatus.ACTIVE
        ).exclude(id=user_company_profile_id)

        return ProfileSerializer(profiles, many=True).data
    
    
class SwitchProfileSerializer(serializers.Serializer):
    pass


class PermissionSerializer(BaseSerializer):
    perm_type = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Permission
        fields = [
            "id",
            "name",
            "codename",
            "type",
            "parent",
            "group",
            "perm_type",
            "children",
        ]

    def get_perm_type(self, instance):
        role_permissions = RolePermission.objects.filter(
            permission=instance, role_id__in=self.context.get("roles", [])
        )

        if not role_permissions.exists():
            return None

        priority_order = [
            PermissionOptions.ALLOWED,
            PermissionOptions.VIEW_ONLY,
            PermissionOptions.DENIED,
        ]
        types = [
            rp.perm_type for rp in role_permissions if rp.perm_type in priority_order
        ]
        types.sort(key=lambda t: priority_order.index(t))
        return types[0] if types else None

    def get_children(self, instance):
        roles = self.context.get("roles", [])
        queryset = Permission.objects.filter(
            parent=instance,

        ).distinct()
        if roles:
            queryset = queryset.filter(role_permissions_related__role_id__in=roles)

        if not queryset.exists():
            return []

        return PermissionSerializer(queryset, many=True, context=self.context).data
