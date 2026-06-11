import logging
from decimal import Decimal

from apps.auth_oauth.mixins.base_encryption_mixins import BaseEncryptionMixins
from apps.core.base import setting_cache as cache


CONST_AUTH_PUBLIC_KEY_PATH = "AUTH_PUBLIC_KEY"
CONST_AUTH_PRIVATE_KEY_PATH = "AUTH_PRIVATE_KEY"
CONST_AUTH_PASSWORD_ENCRYPTION = "AUTH_PASSWORD_ENCRYPTION"


class EncryptionMixin(BaseEncryptionMixins):
    """The class use for Encrypt and Decrypt Password or PIN code

    Args:
        BaseEncryptionMixins (class): for Encrypt and Decrypt Password or PIN code.
    """

    def __init__(
        self,
        request=None,
        is_enabled=None,
        public_key_path=None,
        private_key_path=None,
    ):
        self.is_enabled = (
            is_enabled
            if is_enabled is not None
            else cache.get_bool(request, CONST_AUTH_PASSWORD_ENCRYPTION)
        )
        self.public_key_path = public_key_path or cache.get_str(
            request, CONST_AUTH_PUBLIC_KEY_PATH
        )
        self.private_key_path = private_key_path or cache.get_str(
            request, CONST_AUTH_PRIVATE_KEY_PATH
        )

        super().__init__(self.private_key_path, self.public_key_path)

    def decrypt_value(self, value: str):
        if self.is_enabled:
            return self.decrypt(value)
        return value

    def encrypt_value(self, value: str):
        if self.is_enabled and value is not None:
            if isinstance(value, Decimal):
                value = str(value)
            return self.encrypt(value.encode()).hex()
        return value
