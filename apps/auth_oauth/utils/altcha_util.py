from altcha import verify_solution
from django.conf import settings


def verify_altcha_or_none(payload):
    """
    Reusable function to verify ALTCHA payload.

    Returns:
        (bool, str|None): (is_valid, error_message)
    """

    hmac_key = getattr(settings, "ALTCHA_HMAC_KEY", "")

    ok, err = verify_solution(payload, hmac_key, True)

    if err:
        return False, err

    if not ok:
        return False, "Invalid ALTCHA solution."

    return True, None
