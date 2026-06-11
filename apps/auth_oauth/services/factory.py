from apps.auth_oauth.constants.auth_constants import AuthenticationProviders
from apps.auth_oauth.services.strategies.apple import AppleOAuthStrategy
from apps.auth_oauth.services.strategies.google import GoogleAuthStrategy
from apps.auth_oauth.services.strategies.linkedin import LinkedInOAuthStrategy


class OAuthProviderStrategyFactory:
    _strategy_map = {
        AuthenticationProviders.GOOGLE: GoogleAuthStrategy,
        AuthenticationProviders.LINKEDIN: LinkedInOAuthStrategy,
        AuthenticationProviders.APPLE: AppleOAuthStrategy
    }

    @staticmethod
    def get_redirect_url(provider_name: str):
        strategy_cls = OAuthProviderStrategyFactory._strategy_map.get(provider_name.lower())
        if not strategy_cls:
            raise ValueError(f"Provider '{provider_name}' not found.")
        return strategy_cls.get_redirect_url()

    @staticmethod
    def verify_token(
            client_id: str, provider_name: str, id_token_value: str, token: str, code: str
    ):
        strategy_cls = OAuthProviderStrategyFactory._strategy_map.get(provider_name.lower())
        if not strategy_cls:
            raise ValueError(f"Provider '{provider_name}' not found.")

        strategy = strategy_cls(client_id=client_id)  # Pass anything needed in __init__
        return strategy.verify_token(id_token_value=id_token_value, token=token, code=code)
