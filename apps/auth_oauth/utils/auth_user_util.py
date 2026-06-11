import logging

from apps.auth_oauth.utils.user_auth_cache import delete_cached_key
from apps.auth_oauth.utils.utils import jwt_decode_rs256_token


logger = logging.getLogger(__name__)


def revoke_access_token(request, verifying_key):
    """
    Extracts access token from Authorization header, decodes it,
    and deletes its jti in Redis to immediately revoke the token.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        logger.info("[AccessRevoke] Authorization header not found.")
        return

    if not auth_header.startswith("Bearer "):
        logger.info("[AccessRevoke] No Bearer token in Authorization header.")
        return

    try:
        access_token_str = auth_header.split(" ")[1]

        # Decode JWT manually with your RS256 decoder (or PyJWT directly)
        access_payload = jwt_decode_rs256_token(
            access_token_str, public_key=verifying_key
        )
        access_jti = access_payload.get("jti")

        if access_jti:
            delete_cached_key(f"access_jti:{access_jti}")
            logger.info(f"[AccessRevoke] Successfully revoked access_jti:{access_jti}")
        else:
            logger.warning(
                "[AccessRevoke] No jti found in decoded access token payload."
            )

    except Exception as e:
        logger.exception(f"[AccessRevoke] Failed to revoke access token: {e}")
