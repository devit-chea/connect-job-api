from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.constants.auth_constants import UserStatus
from apps.auth_oauth.utils.utils import increase_email_sequence
from environs import env

env.read_env()


class UserValidation:

    def validate_existed_email(self, username):
        user = User.objects.filter(username=username).order_by("-id").first()
        if not user:
            return
        user.email = increase_email_sequence(user.email, user.number_of_created)
        user.status = UserStatus.INACTIVE
        user.is_active = False
        user.save()
        return user.number_of_created
    
