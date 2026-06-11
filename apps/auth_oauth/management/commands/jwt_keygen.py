import os
from django.core.management.base import BaseCommand, CommandError

from auth_oauth.constants.jwt_constants import (
    CONST_JWT_VERIFYING_KEY_PATH,
    CONST_JWT_SIGNING_KEY_PATH,
)
from apps.base.mixins.encryption_mixins import EncryptionMixins

from config.config_loader import load_config


APP_CONFIG = load_config()

class Command(BaseCommand):
    help = "Runs to generate keys for jwt signing_key and verifying_key"

    def handle(self, *args, **options):
        encryption = EncryptionMixins(
            public_key_path=APP_CONFIG.get(CONST_JWT_VERIFYING_KEY_PATH),
            private_key_path=APP_CONFIG.get(CONST_JWT_SIGNING_KEY_PATH),
        )

        # Create folder if not exists
        os.makedirs(os.path.dirname(encryption.private_key_path), exist_ok=True)
        os.makedirs(os.path.dirname(encryption.public_key_path), exist_ok=True)

        if os.path.exists(encryption.private_key_path) or os.path.exists(
            encryption.public_key_path
        ):
            confirm = input(
                "The file is already exists. Do you want to overwrite it? :(y/n) "
            ).lower()
            if confirm not in ["y", "yes"]:
                raise CommandError("File generation canceled.")

        encryption.generate_rsa()

        self.stdout.write(
            self.style.SUCCESS("jwt keygen is successfully generated.")
        )
