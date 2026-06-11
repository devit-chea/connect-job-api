from ..config import Configs
from ..models import AuthSettingModel
         
# Enable email otp confirmation 
def is_enable_totp_mail(user: object, app_name: str)->bool:
    value = Configs._bool_setting('ENABLE_AUTH_TOTP_MAIL', user.base_company_id)
    if value:
        return True
    
    auth_setting = AuthSettingModel.objects.filter(user=user,app_name=app_name).first()
    if auth_setting and auth_setting.is_enable:
        return True
    return False

# Enable email otp confirmation 
def toggle_auth_totp_mail(request, user_obj, app_name:str = "auth_totp_mail"):
    try:
        is_enable = user_obj.is_two_step_verification
        AuthSettingModel.objects.update_or_create(
            user=user_obj,
            app_name=app_name,
            defaults={
                "is_enable": is_enable,
                "write_uid": request.user.id
            }
        )
    except Exception:
        # The caught exception is printed for debugging purposes
        toggle = "enabled" if is_enable else "disabled"
        print(f"invalid user for {toggle} 2-Step Verification.")



