from apps.auth_oauth.utils.auth_util import is_jwt_token_expired, del_jwt_response_cookie
from config.settings import base as settings


class RemoveExpiredJwtMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._del_access_token(request, response)
        self._del_refresh_token(request, response)

        return response

    @staticmethod
    def _del_access_token(request, response):
        access_cookie_name = settings.SIMPLE_JWT["ACCESS_COOKIE"]
        access_token = getattr(response.cookies.get(access_cookie_name), "value", None)
        if not access_token:
            access_token = request.COOKIES.get(access_cookie_name)
        if access_token and is_jwt_token_expired(access_token):
            del_jwt_response_cookie(
                response,
                is_remove_access=True,
                is_remove_refresh=False,
            )

    @staticmethod
    def _del_refresh_token(request, response):
        refresh_cookie_name = settings.SIMPLE_JWT["REFRESH_COOKIE"]
        refresh_token = getattr(
            response.cookies.get(refresh_cookie_name), "value", None
        )
        if not refresh_token:
            refresh_token = request.COOKIES.get(refresh_cookie_name)
        if refresh_token and is_jwt_token_expired(refresh_token):
            del_jwt_response_cookie(
                response,
                is_remove_access=False,
                is_remove_refresh=True,
            )


class JwtCookieAccessTokenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        access_cookie_name = settings.SIMPLE_JWT["ACCESS_COOKIE"]
        access_token = request.COOKIES.get(access_cookie_name)
        if access_token:
            request.META["HTTP_AUTHORIZATION"] = f"Bearer {access_token}"
        response = self.get_response(request)
        return response
