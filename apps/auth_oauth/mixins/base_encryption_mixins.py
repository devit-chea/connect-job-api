import re
import logging

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

logger = logging.getLogger(__name__)


class BaseEncryptionMixins:
    def __init__(self, private_key_path, public_key_path):
        self.private_key = private_key_path
        self.public_key = public_key_path

    def _read_private_key(self):
        try:
            key_str = self.private_key
            if not key_str:
                raise KeyError(f"Environment variable {self.private_key} is not set")
            key_str = key_str.replace("\\n", "\n")
            key_str = re.sub(r"\\+", "", key_str)
            key_str = key_str.strip()

            key_bytes = key_str.encode("utf-8")
            private_key = serialization.load_pem_private_key(
                key_bytes,
                password=None,
                backend=default_backend(),
            )
            return private_key

        except KeyError as e:
            logger.error(f"[PrivateKey] Missing environment variable: {e}")
            raise KeyError(f"Failed to load key: {str(e)}")
        except ValueError as e:
            logger.error(f"[PrivateKey] Failed to decode PEM key: {e}")
            raise ValueError(f"Failed to decode key: {str(e)}")

        except Exception as e:
            logger.exception(f"[PrivateKey] Unexpected error while loading key: {e}")
            raise ValueError(f"Unexpected error loading key: {str(e)}")

    def _get_private_key(self):
        private_key_bytes = self._read_private_key()

        return private_key_bytes

    def _get_public_key(self):
        try:
            key_str = self.public_key
            if not key_str:
                raise KeyError(f"Environment variable {self.public_key} is not set")
            key_str = key_str.replace("\\n", "\n")
            key_str = re.sub(r"\\+", "", key_str)
            key_str = key_str.strip()
            key_bytes = key_str.encode("utf-8")
            public_key = serialization.load_pem_public_key(
                key_bytes, backend=default_backend()
            )
            return public_key

        except KeyError as e:
            raise KeyError(f"Failed to load key: {str(e)}")
        except ValueError as e:
            raise ValueError(f"Failed to decode key: {str(e)}")

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
            raise ValueError({"error": "No such as file or directory."})
        except Exception as e:
            raise ValueError({"error": "Data provided is not valid."})

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
            logger.error(f"[Decrypt] Private key file not found: {e}")
            raise ValueError({"error": "No such as file or directory."})
        except Exception as e:
            logger.exception(f"[Decrypt] Invalid data or decryption failure: {e}")
            raise ValueError(f"Data provided is not valid, {e}")
