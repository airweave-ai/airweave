"""Schemas for integration auth settings."""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


class AuthType(str, Enum):
    """Enumeration of supported authentication types.

    Attributes:
    ----------
        oauth2: OAuth2 authentication.
        oauth2_with_refresh: OAuth2 authentication with refresh token.
        oauth2_with_refresh_rotating: OAuth2 authentication with rotating refresh token.
        trello_auth: Trello authentication.
        api_key: API key authentication.
        native_functionality: Native functionality.
        url_and_api_key: URL and API key authentication.
        none: No authentication.
    """

    oauth2 = "oauth2"
    oauth2_with_refresh = "oauth2_with_refresh"
    oauth2_with_refresh_rotating = "oauth2_with_refresh_rotating"
    trello_auth = "trello_auth"
    api_key = "api_key"
    native_functionality = "native_functionality"
    config_class = "config_class"
    sigv4 = "sigv4"
    none = "none"


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
        auth_type (AuthType): The authentication type.

    """

    auth_type: AuthType


class TrelloAuthSettings(BaseAuthSettings):
    """Trello authentication settings schema.

    Attributes:
    ----------
        key (str): The Trello API key.
        url (str): The Trello authorization URL.
        scope (str): The scope of the authorization.
        callback_method (str): The callback method.
        expiration (str): The expiration time.
        name (str): The name of the integration.

    """

    key: str
    url: str
    scope: str
    callback_method: str
    expiration: str
    name: str


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


class SigV4Settings(BaseAuthSettings):
    """SigV4 authentication settings."""

    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    session_token: Optional[str] = None

    endpoint_url: Optional[str] = None
    name: Optional[str] = None
    region: Optional[str]
    bucket: Optional[str]


class OAuth2WithRefreshSettings(OAuth2Settings):
    """OAuth2 with refresh token settings schema."""

    pass


class OAuth2WithRefreshRotatingSettings(OAuth2Settings):
    """OAuth2 with rotating refresh token settings schema."""

    pass


class ConfigClassAuthSettings(BaseAuthSettings):
    """Config class authentication settings schema."""

    pass
