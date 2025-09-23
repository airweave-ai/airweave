"""Schemas for integration auth settings."""

from typing import Any, Optional

from pydantic import BaseModel, model_validator


class OAuth2TokenResponse(BaseModel):
    """OAuth2 token response schema.

    Attributes:
    ----------
        access_token (str): The access token.
        token_type (Optional[str]): The token type.
        expires_in (Optional[int]): The expiration time in seconds.
        refresh_token (Optional[str]): The refresh token.
        scope (Optional[str]): The scope of the token.
        extra_fields (dict[str, Any]): Extra fields.
    """

    access_token: str
    token_type: Optional[str] = None
    expires_in: Optional[int] = None
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    extra_fields: dict[str, Any] = {}

    class Config:
        """Pydantic configuration.

        Attributes:
        ----------
            extra: Configuration to allow extra fields.

        """

        extra = "allow"


class BaseAuthSettings(BaseModel):
    """Base authentication settings schema.

    Attributes:
    ----------
        integration_short_name: The short name of the integration.
        authentication_method: The authentication method (OAUTH_BROWSER, OAUTH_TOKEN, DIRECT, etc.).
        oauth_type: The OAuth type if applicable (ACCESS_ONLY, WITH_REFRESH, WITH_ROTATING_REFRESH).

    """

    integration_short_name: Optional[str] = None
    authentication_method: Optional[str] = None  # AuthenticationMethod value
    oauth_type: Optional[str] = None  # OAuthType value if OAuth


class NativeFunctionalityAuthSettings(BaseAuthSettings):
    """Native authentication settings schema."""

    pass


class APIKeyAuthSettings(BaseAuthSettings):
    """API key authentication settings schema."""

    pass


class URLAndAPIKeyAuthSettings(BaseAuthSettings):
    """URL and API key authentication settings schema."""

    pass


class OAuth2Settings(BaseAuthSettings):
    """OAuth2 authentication settings schema.

    Attributes:
    ----------
        integration_short_name (str): The integration short name.
        url (str): The authorization URL.
        backend_url (str): The backend URL.
        grant_type (str): The grant type.
        client_id (str): The client ID.
        client_secret (Optional[str]): The client secret. Only in dev.integrations.yaml.
        content_type (str): The content type.
        client_credential_location (str): The client credential location.
        additional_frontend_params (Optional[dict[str, str]]): Additional frontend parameters.
        scope (Optional[str]): The scope.

    """

    integration_short_name: str
    url: str
    backend_url: str
    grant_type: str
    client_id: str
    client_secret: Optional[str] = None
    content_type: str
    client_credential_location: str
    additional_frontend_params: Optional[dict[str, str]] = None
    scope: Optional[str] = None

    @model_validator(mode="after")
    def validate_oauth_fields(self):
        """Validate that OAuth integrations have required fields."""
        if not self.url:
            raise ValueError(f"OAuth integration {self.integration_short_name} missing 'url' field")
        if not self.backend_url:
            raise ValueError(
                f"OAuth integration {self.integration_short_name} missing 'backend_url' field"
            )
        if not self.client_id:
            raise ValueError(
                f"OAuth integration {self.integration_short_name} missing 'client_id' field"
            )
        return self


class OAuth2WithRefreshSettings(OAuth2Settings):
    """OAuth2 with refresh token settings schema."""

    pass


class OAuth2WithRefreshRotatingSettings(OAuth2Settings):
    """OAuth2 with rotating refresh token settings schema."""

    pass


class ConfigClassAuthSettings(BaseAuthSettings):
    """Config class authentication settings schema."""

    pass


class OAuth2AuthUrl(BaseModel):
    """OAuth2 authorization URL schema.

    Attributes:
    ----------
        url (str): The authorization URL.
    """

    url: str
