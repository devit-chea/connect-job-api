from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
import os
from apps.base.utils.settings_util import Settings
from rest_framework import serializers

from apps.base.cache.cached_decorator import cached

CONST_DIRECTORY = os.path.join('storages','security')
CONST_PRIVATE_KEY = "private_key.pem"
CONST_PUBLIC_KEY = "public_key.pem"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CONST_PRIVATE_KEY_PATH = os.path.join(BASE_DIR, CONST_DIRECTORY, CONST_PRIVATE_KEY)
CONST_PUBLIC_KEY_PATH =  os.path.join(BASE_DIR, CONST_DIRECTORY, CONST_PUBLIC_KEY)


def _check_directory():
    if not os.path.exists(os.path.join(BASE_DIR,CONST_DIRECTORY)):
        os.makedirs(os.path.join(BASE_DIR,CONST_DIRECTORY))

    if not os.path.exists(CONST_PRIVATE_KEY_PATH):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        with open(CONST_PRIVATE_KEY_PATH, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        with open(CONST_PUBLIC_KEY_PATH, "wb") as f:
            f.write(
                private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )

def _get_private_key():
    _check_directory()
    private_key = None

    private_key_bytes = _read_private_key()

    private_key = serialization.load_pem_private_key(
        private_key_bytes,
        password=None,
    )

    return private_key

@cached(timeout=3600)
def _read_private_key():
    with open(CONST_PRIVATE_KEY_PATH, "rb") as f:
        private_key_bytes = f.read()
    return private_key_bytes

def decrypted_password(password):
    if not Settings.get_system_setting("PASSWORD_ENCRYPTION"):
        return password

    if password:
        return _decrypted_password(password)

    _invalid_email_or_password()


def _decrypted_password(password):
    try:
        plaintext = _get_private_key().decrypt(
            bytes.fromhex(password),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return plaintext.decode("utf-8")
    except Exception:
        _invalid_email_or_password()


def _invalid_email_or_password():
    raise serializers.ValidationError(detail={"message": ["Invalid email or password"]})


def get_public_key_string():
    return (
        _get_private_key()
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


def encrypt_password(password):
    return (
        _get_private_key()
        .public_key()
        .encrypt(
            password.encode(),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
    )

def check_rsa_key():
    _check_directory()