from django.db.models import Q
from rest_framework import serializers

from apps.auth_oauth.constants.auth_constants import UserState, UserStatus
from apps.auth_oauth.models.auth_models import User


class UserService:

    @staticmethod
    def update_fname_and_lname(id, validated_data):
        """
        method update user first_name and last_name
        """
        User.objects.filter(pk=id).update(
            first_name=validated_data.get("first_name", None),
            last_name=validated_data.get("last_name", None),
        )

    @staticmethod
    def validate_user(username, email, exclude_id=None):
        user_query = User.objects.filter(
            ~Q(state=UserState.PENDING_VERIFY_OPT),
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        if exclude_id:
            user_query = user_query.exclude(pk=exclude_id)

        existed_user = user_query.filter(username=username).exists()
        existed_email = user_query.filter(email=email).exists()
        if existed_user:
            raise serializers.ValidationError(
                {"username": "A user with this username already exists."}
            )
        if existed_email:
            raise serializers.ValidationError(
                {"email": "A user with this email already exists."}
            )
