from rest_framework import status
from django.middleware import csrf
from django.contrib.auth import logout
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.tokens import RefreshToken
from apps.auth_oauth.constants.auth_constants import UserStatus, UserState

from apps.auth_oauth.constants.jwt_constants import TokenTypeHeader
from apps.auth_oauth.utils.auth_util import set_jwt_response_cookie, generate_jwt_token


def get_device_info(request):
    return {
        "ip_address": request.META.get("HTTP_X_FORWARDED_FOR"),
        "user_agent": request.META.get("HTTP_USER_AGENT"),
    }


def get_or_create_user_token(user):
    token, _ = Token.objects.get_or_create(user=user)
    return token.key


def issue_token_to_user(
    request, user, is_verify_otp=None, user_company_profile_id=None
):
    csrf.get_token(request)
    request.session["device_info"] = get_device_info(request)
    request.session.save()
    # active user
    if is_verify_otp:
        user.status = UserStatus.ACTIVE
        user.state = UserState.COMPLETE_VERIFY_OPT
        user.is_active = True
        user.is_login = True
        user.save()

    if not user_company_profile_id:
        user_company_profile_id = request.data.get("user_company_profile_id", None)
    access, refresh = generate_jwt_token(user, request, user_company_profile_id)
    response = Response(
        {"access": access, "refresh": refresh}, status=status.HTTP_200_OK
    )

    set_jwt_response_cookie(
        response,
        response.data["access"],
        response.data["refresh"],
    )
    return response


def logout_util(request, user):
    token = request.META.get("HTTP_AUTHORIZATION")
    if user and token:
        token_instances = Token.objects.filter(user=user.id)
        token_instances.delete()

    logout(request)
    refresh_token = request.data.get("refresh_token")
    token = RefreshToken(token=refresh_token)
    token.blacklist()
    response = {"message": "Logout Successful"}
    return Response(data=response, status=status.HTTP_200_OK)
