import binascii
import datetime
import hashlib
import hmac
import os
import secrets
import time
import logging

import pyotp
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django_user_agents.utils import get_user_agent
from environs import env
from rest_framework import serializers
from django.core.cache import cache

from apps.auth_oauth.security.asymmetric_encryption import _decrypted_password
from apps.auth_setting.config import Configs
from apps.base.constants.base_constants import ENV
from apps.core.exceptions.base_exceptions import (
    BadRequestException,
    ExpiredException,
)

env.read_env()

logger = logging.getLogger(__name__)


class Data:
    def __init__(self, otp, otp_encrypted, otp_expiry, user_agent, ip_address):
        self.otp = otp
        self.otp_encrypted = otp_encrypted
        self.otp_expiry = otp_expiry
        self.user_agent = user_agent
        self.ip_address = ip_address


def retry_in_to_timestamp(company: int = None):
    retry_in = Configs._int_setting("OTP_RETRY_IN_SECONDS", company)
    retry_in_time = datetime.datetime.now() + datetime.timedelta(seconds=retry_in)
    return int(retry_in_time.timestamp())


def generate_key_confirm():
    return binascii.hexlify(os.urandom(20)).decode()


def generate_single_use_token(user_id: int):
    client = cache
    secret = settings.SINGLE_USE_TOKEN_SECRET.encode()

    iat = int(time.time())  # issued_at
    expiry_seconds = getattr(settings, "RESET_PASS_TOKEN_EXPIRY_SECONDS", 900)
    exp = iat + expiry_seconds
    nonce = secrets.token_hex(16)  # ensure uniqueness

    payload_str = f"{user_id}:{iat}:{exp}:{nonce}"
    payload_bytes = payload_str.encode()

    signature = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()

    token = f"{payload_str}:{signature}"
    if client:
        USED_KEY = f"single_use_token:{signature}"
        client.set(USED_KEY, "valid", expiry_seconds)
    return token


def validate_single_use_token(token: str):
    client = cache
    logger.info("Validating single-use token")
    try:
        user_id, iat, exp, nonce, signature = token.split(":")
        user_id = int(user_id)
        iat = int(iat)
        exp = int(exp)
        logger.debug(f"Token parsed successfully | user_id={user_id}, exp={exp}")
    except Exception as e:
        logger.error(f"Token parsing failed | error={str(e)} | token={token}")
        return None

    current_time = int(time.time())
    if current_time > exp:
        logger.warning(
            f"Token expired | user_id={user_id} | exp={exp} | current_time={current_time}"
        )
        return None

    # Rebuild signature
    try:
        secret = settings.SINGLE_USE_TOKEN_SECRET.encode()
        payload = f"{user_id}:{iat}:{exp}:{nonce}"
        expected_signature = hmac.new(
            secret, payload.encode(), hashlib.sha256
        ).hexdigest()
    except Exception as e:
        logger.error(f"Signature generation failed | user_id={user_id} | error={str(e)}")
        return None

    if not hmac.compare_digest(signature, expected_signature):
        logger.warning(
            f"Invalid token signature detected | user_id={user_id}"
        )
        return None  # tampered token

    if client:
        USED_KEY = f"single_use_token:{signature}"
        try:
            status = client.get(USED_KEY)
            logger.debug(f"Cache lookup | key={USED_KEY} | status={status}")

            if status is None:
                logger.warning(f"Token already used or expired in cache | user_id={user_id}")
                return None
        except Exception as e:
            logger.error(
                f"Cache check failed | user_id={user_id} | error={str(e)}"
            )
            return None

    logger.info(f"Token validated successfully | user_id={user_id}")
    return user_id


def mark_as_used(token: str):
    """Mark the token as used in Redis."""
    client = cache
    try:
        _, _, _, _, signature = token.split(":")
    except Exception as e:
        logger.error(f"mark_as_used parse failed | error={str(e)}")
        return
    if client:
        USED_KEY = f"single_use_token:{signature}"
        client.delete(USED_KEY)
        logger.debug(f"Token consumed | key={USED_KEY}")


def generate_otp_instance(request, company: int = None):
    user_agent = request.META[Configs._setting("HTTP_USER_AGENT_HEADER", company)]
    ip_address = request.META[Configs._setting("HTTP_IP_ADDRESS_HEADER", company)]
    # Time-based OTPs
    secrete_key_random = pyotp.random_base32()

    otp_expiry_sys = Configs._int_setting("OTP_EXPIRY_IN_SECONDS", company)
    totp = pyotp.TOTP(secrete_key_random, digits=6, interval=otp_expiry_sys)
    otp_expiry = timezone.now() + datetime.timedelta(seconds=otp_expiry_sys)
    otp = totp.now()
    
    otp_as_password = make_password(otp)

    # Create an instance of the Data class
    return Data(
        otp,
        otp_as_password,
        otp_expiry,
        user_agent,
        ip_address,
    )


# Convert: OTP_EXPIRY_IN_SECONDS
def time_format(seconds) -> str:
    """
    :param seconds: the time in seconds.
    """
    if seconds is not None:
        seconds = int(seconds)
        d = seconds // (3600 * 24)
        h = seconds // 3600 % 24
        m = seconds % 3600 // 60
        s = seconds % 3600 % 60
        if d > 0:
            return "{:2d}D {:2d}H {:2d}m {:2d}s".format(d, h, m, s)
        elif h > 0:
            return "{:2d}H {:2d}m {:2d}s".format(h, m, s)
        elif m > 0:
            return "{:2d}m {:2d}s".format(m, s)
        elif s > 0:
            return "{:2d}s".format(s)
    return "-"


# *** Accessor User Agents
def access_user_agents_parse(request) -> str:
    user_agent = get_user_agent(request)
    if not user_agent:
        return ""

    if user_agent.is_pc:
        device_name = user_agent.browser.family
    elif user_agent.is_mobile:
        device_name = user_agent.device.family
    else:
        device_name = "Unknown"

    os_name = user_agent.os.family if user_agent.os else "Unknown"
    return f"{os_name}, {device_name}"


def template_context(request, totpmail: object, otp) -> dict:
    template_context = dict(Configs._setting("AUTH_TOTP_MAIL_TEMPLATE_CONTEXT"))

    template_context["otp"] = otp
    template_context["send_at"] = totpmail.send_at
    template_context["recipient"] = totpmail.email
    template_context["user_id"] = totpmail.user.id
    template_context["username"] = totpmail.user.username
    template_context["first_name"] = totpmail.user.first_name
    template_context["user_agent"] = access_user_agents_parse(request)
    template_context["expire_in"] = time_format(
        Configs._int_setting("OTP_EXPIRY_IN_SECONDS", totpmail.company_id)
    )

    template_context["location"] = None
    template_context["link_confirm"] = None

    return template_context


def verify_totp_confirmation_and_get_user(confirm_key, otp_encrypted):
    from apps.auth_totp_mail.models import TotpMailConfirmation

    try:
        # Use select_related to efficiently fetch the related user and company data if needed later
        confirmation = TotpMailConfirmation.objects.select_related("user").get(
            confirm_key=confirm_key
        )
    except TotpMailConfirmation.DoesNotExist:
        raise BadRequestException("Invalid confirmation details.")
    except serializers.ValidationError:
        raise BadRequestException("You enter an invalid code. Please try again!")
    if confirmation._otp_expiry():
        raise ExpiredException("Email confirmation expired, Please request a new one.")
    is_otp_encryption = Configs._bool_setting(
        "PASSWORD_ENCRYPTION", confirmation.company_id
    )
    raw_otp = _decrypted_password(otp_encrypted) if is_otp_encryption else otp_encrypted
    if not check_password(raw_otp, confirmation.otp_encryption):
        # Handle failed attempts logging
        confirmation._failed_confirm()

        # Verify OPT attempt limit
        otp_verify_attempt_limit = Configs._int_setting(
            "OTP_VERIFY_ATTEMPT_LIMIT", confirmation.company_id
        )
        if confirmation.failed_confirm >= otp_verify_attempt_limit:
            confirmation.clean()  # Assuming clean() finalizes the attempt limit logic
            raise BadRequestException(
                "OPT verify reach attempt limit, Please request a new one."
            )
        raise BadRequestException("You enter an invalid code. Please try again!")

    # If successful, mark the confirmation as used and finalize it
    user = confirmation.user
    confirmation.confirmed_at = timezone.now()
    confirmation.save(update_fields=("confirmed_at",))
    confirmation.clean()
    return user
