import logging
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from django.conf import settings

from apps.core.exceptions.base_exceptions import BadRequestException


class EncryptionMixins:
    def __init__(self, private_key_path, public_key_path):
        self.private_key_path = private_key_path
        self.public_key_path = public_key_path

    def encrypt(self, data):
        try:
            public_key = self._get_public_key()
            ciphertext = public_key.encrypt(
                data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )

            return ciphertext
        except FileNotFoundError as e:
            logging.error(e)
            raise BadRequestException("No such as file or directory.")

        except Exception as e:
            logging.error(e)
            raise BadRequestException("Data provided is not valid.")

    def decrypt(self, data):
        try:
            plaintext = self._get_private_key().decrypt(
                bytes.fromhex(data),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
            return plaintext.decode("utf-8")

        except FileNotFoundError as e:
            logging.error(e)
            raise BadRequestException("No such as file or directory.")
        except Exception as e:
            logging.error(e)
            raise BadRequestException("Data provided is not valid.")

    def generate_rsa(self):
        try:
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            with open(self.private_key_path, "wb") as f:
                f.write(
                    private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption(),
                    )
                )

            with open(self.public_key_path, "wb") as f:
                f.write(
                    private_key.public_key().public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                )
        except FileNotFoundError as e:
            logging.error(e)

    def _get_public_key(self):
        with open(os.path.join(settings.BASE_DIR, self.public_key_path), "rb") as f:
            public_key = serialization.load_pem_public_key(f.read())
        return public_key

    def _get_private_key(self):
        private_key_bytes = self._read_private_key()
        return serialization.load_pem_private_key(
            private_key_bytes,
            password=None,
        )

    def _read_private_key(self):
        with open(os.path.join(settings.BASE_DIR, self.private_key_path), "rb") as f:
            private_key_bytes = f.read()
        return private_key_bytes

