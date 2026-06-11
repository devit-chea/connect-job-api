import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from apps.auth_oauth.mixins.encryption_mixins import EncryptionMixin

class CustomPasswordValidator:
    def validate(self, password, user=None): # "user" is unused
        min_length = 8
        max_length = 512
        
        encrypted_password = password
        try:
            encryption = EncryptionMixin()
            password = encryption.decrypt_value(encrypted_password)
        except Exception:
            raise ValidationError(
                _(f"Unable to create the account.")
            )
            
        if len(password) < min_length:
            raise ValidationError(
                _(f"Password must be at least {min_length} characters long.")
            )

        if len(password) > max_length:
            raise ValidationError(
                _(
                    f"Password must be at most {max_length} characters long (you provided {len(password)})."
                )
            )

        if not re.search(r"[A-Z]", password):
            raise ValidationError(
                _("Password must contain at least one uppercase letter.")
            )

        if not re.search(r"[a-z]", password):
            raise ValidationError(
                _("Password must contain at least one lowercase letter.")
            )

        if not re.search(r"\d", password):
            raise ValidationError(_("Password must contain at least one number."))

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise ValidationError(
                _("Password must contain at least one special character.")
            )

    def get_help_text(self):
        return _(
            "Your password must be 8 to 50 characters long, include upper and lower case letters, "
            "at least one number, and one special character."
        )
