from rest_framework.exceptions import APIException
from django.utils.translation import gettext_lazy as _
from rest_framework import status


class BaseException(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = _("A server error occurred.")
    default_code = "error"


class BadRequestException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _("A bad request occurred.")
    default_code = "error"


class UnauthorizedException(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _("A unauthorized request occurred.")
    default_code = "error"


class NotFoundException(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _("Record not found.")
    default_code = "error"


class InvalidToken(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _("Token is invalid or expired")
    default_code = "token_not_valid"


class ExpiredException(APIException):
    status_code = status.HTTP_410_GONE
    default_detail = _("expired")
    default_code = "error"


class PermissionDeniedException(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _("You do not have permission to perform this action.")
    default_code = "permission_denied"
