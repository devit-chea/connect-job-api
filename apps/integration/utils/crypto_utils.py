import base64
import hashlib
import os

from django.conf import settings
from django.db import models
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


NONCE_LENGTH = 12


def get_encryption_key() -> bytes:
    """
    AES-256 requires a 32-byte key.

    Generate:
        import os, base64
        print(base64.urlsafe_b64encode(os.urandom(32)).decode())
    """

    key = getattr(settings, "CONNECTOR_INTEGRATION_KEY", None)
    if not key:
        raise ValueError("CONNECTOR_INTEGRATION_KEY is not configured")

    try:
        decoded_key = base64.urlsafe_b64decode(key)
    except Exception as exc:
        raise ValueError(
            "CONNECTOR_INTEGRATION_KEY must be a valid Base64 string"
        ) from exc
    if len(decoded_key) != 32:
        raise ValueError(
            "CONNECTOR_INTEGRATION_KEY must decode to exactly 32 bytes"
        )

    return decoded_key


def encrypt_aes_256_gcm(text: str) -> str:
    """
    Returns:
        base64(nonce + ciphertext_and_tag)
    """

    if not text:
        return ""

    nonce = os.urandom(NONCE_LENGTH)
    aesgcm = AESGCM(get_encryption_key())

    encrypted = aesgcm.encrypt(
        nonce=nonce,
        data=text.encode("utf-8"),
        associated_data=None,
    )

    return base64.urlsafe_b64encode(
        nonce + encrypted
    ).decode("utf-8")


def decrypt_aes_256_gcm(encrypted_payload: str) -> str:
    """
    Accepts:
        base64(nonce + ciphertext_and_tag)
    """

    if not encrypted_payload:
        return ""

    try:
        raw = base64.urlsafe_b64decode(
            encrypted_payload.encode("utf-8")
        )

        nonce = raw[:NONCE_LENGTH]
        ciphertext = raw[NONCE_LENGTH:]

        aesgcm = AESGCM(get_encryption_key())

        decrypted = aesgcm.decrypt(
            nonce=nonce,
            data=ciphertext,
            associated_data=None,
        )

        return decrypted.decode("utf-8")

    except Exception as exc:
        raise ValueError(
            "Decryption failed. Invalid payload or encryption key."
        ) from exc


def hash_sha256(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def base64url_encode_sha256(text: str) -> str:
    digest = hashlib.sha256(
        text.encode("utf-8")
    ).digest()

    return (
        base64.urlsafe_b64encode(digest)
        .decode("utf-8")
        .rstrip("=")
    )


class EncryptedTextField(models.TextField):
    """
    Transparent AES-256-GCM field encryption.

    Database:
        encrypted value

    Python:
        plain text
    """

    def get_prep_value(self, value):
        value = super().get_prep_value(value)

        if value is None:
            return value

        return encrypt_aes_256_gcm(str(value))

    def from_db_value(
        self,
        value,
        expression,
        connection,
    ):
        if value is None:
            return value

        return decrypt_aes_256_gcm(value)

    def to_python(self, value):
        if value is None:
            return value

        # already converted
        if not isinstance(value, str):
            return value

        return value