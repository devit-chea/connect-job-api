import logging
import secrets

from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.utils.redis_cache import (
    set_cached_json,
    get_cached_json,
    delete_cached_key,
)

TELEGRAM_LINK_TOKEN_TTL = 600

logger = logging.getLogger(__name__)


def send_otp_via_telegram(telegram_chat_id: str, otp: str) -> bool:
    """
    Send OTP to the user's Telegram chat.
    telegram_chat_id is stored on User.telegram_chat_id after the user
    initiates the bot flow (bot receives /start and stores chat_id).
    Returns False if the chat_id is not yet linked.
    """
    if not telegram_chat_id:
        return False

    import requests
    from django.conf import settings

    bot_token = settings.TELEGRAM_BOT_TOKEN
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": telegram_chat_id,
        "text": (
            f"Your verification code is: *{otp}*\n"
            f"It expires in 2 minutes. Do not share it."
        ),
        "parse_mode": "Markdown",
    }
    try:
        logger.info(f"Sending OTP via telegram::::{telegram_chat_id}")
        resp = requests.post(url, json=payload, timeout=5)
        logger.info(f"Telegram API Response:::::: {resp.status_code} body {resp.json()}")
        return resp.ok
    except requests.RequestException:
        return False


def generate_telegram_link_token(user, otp: str) -> str:
    token = secrets.token_urlsafe(32)

    User.objects.filter(pk=user.pk).update(telegram_link_token=token)
    # todo uncomment after test
    # set_cached_json(
    #     key=f"tg_link_token:{token}",
    #     value={"user_id": user.pk, "cf_key": otp},
    #     ttl=TELEGRAM_LINK_TOKEN_TTL,
    # )


    return token


def build_telegram_deep_link(token: str) -> str:
    from django.conf import settings

    return f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={token}"


def resolve_link_token(token: str):
    # todo uncomment after test
    data = get_cached_json(f"tg_link_token:{token}")
    if not data:
        logger.info("Catch not found.")
        return None
    user_id = data.get("user_id")
    cf_key = data.get("cf_key")
    return {
        "user_id": user_id,
        "cf_key": cf_key,
    }


def revoke_link_token(token: str):
    delete_cached_key(f"tg_link_token:{token}")
