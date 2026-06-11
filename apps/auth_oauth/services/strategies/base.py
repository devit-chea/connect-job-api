from abc import abstractmethod, ABC


class OAuthProviderStrategy(ABC):
    @abstractmethod
    def verify_token(self, id_token_value: str, token: str, code: str | None = None) -> str:
        """Verify the provider's ID token and return the user data."""
        pass
