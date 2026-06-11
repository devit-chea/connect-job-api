from datetime import datetime
from django_user_agents.utils import get_user_agent
from config.settings.base import API_BASE_URL
from apps.base.utils.settings_util import get_web_base_url

# *** Accessor User Agents
def user_agents_parse(request):
    user_agent = get_user_agent(request)
    device_name = "N/A"
    os_name = 'N/A'
    if not user_agent: return f"{os_name}, {device_name}" 
    
    if user_agent.is_pc:        
        device_name = user_agent.browser.family
    elif user_agent.is_mobile:
        device_name = user_agent.device.family
    # elif user_agent.is_tablet:
    # elif user_agent.is_touch_capable:
    # elif user_agent.is_bot:

    os_name = user_agent.os.family
    return f"{os_name}, {device_name}"

def reset_pass_template_context(request, reset_password_token)->dict:
    now = datetime.now()
    formatted_datetime = now.strftime("%B %d, %Y, %I:%M %p")

    template_context = {
        'send_at': formatted_datetime,
        'user_id':reset_password_token.user.id,
        'recipient': reset_password_token.user.email,
        'username': reset_password_token.user.username,
        'first_name': reset_password_token.user.first_name,
        'user_agent': user_agents_parse(request),
        'logo_reset_password': f"{API_BASE_URL}/static/assets/logo_reset_password.svg",
        'logo_transparency': f"{API_BASE_URL}/static/assets/logo_transparency.png",
        'reset_link': f"{get_web_base_url()}/auth/change-password?token={reset_password_token.key}",
        'location': None
    }
    return template_context