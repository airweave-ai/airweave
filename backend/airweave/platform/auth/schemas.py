"""Schemas for integration auth settings."""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, model_validator


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

    model_config = ConfigDict(extra="allow")


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
        url (str): The authorization URL (may contain {placeholders} for templates).
        backend_url (str): The backend URL (may contain {placeholders} for templates).
        grant_type (str): The grant type.
        client_id (str): The client ID.
        client_secret (Optional[str]): The client secret. Only in dev.integrations.yaml.
        content_type (str): The content type.
        client_credential_location (str): The client credential location.
        additional_frontend_params (Optional[dict[str, str]]): Additional frontend params.
        scope (Optional[str]): The scope for bot tokens (OAuth2).
        user_scope (Optional[str]): The scope for user tokens (OAuth2, used by Slack).
        url_template (bool): Whether url contains template variables (default: False).
        backend_url_template (bool): Whether backend_url has templates (default: False).
        requires_pkce (bool): Whether this OAuth provider requires PKCE
            (Proof Key for Code Exchange). PKCE is a security extension that
            prevents authorization code interception. Set to True for providers
            like Airtable that mandate PKCE.

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
    user_scope: Optional[str] = None
    requires_pkce: bool = False

    # Template support for instance-specific OAuth URLs
    url_template: bool = False
    backend_url_template: bool = False

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

    def render_url(self, **template_vars) -> str:
        """Render URL with template variables.

        Args:
            **template_vars: Variables to interpolate (e.g., instance_url="example.com")

        Returns:
            Rendered URL with variables replaced

        Raises:
            KeyError: If template variable missing

        Example:
            >>> settings.url = "https://{instance_url}/oauth/authorize"
            >>> settings.render_url(instance_url="example.com")
            'https://example.com/oauth/authorize'
        """
        if self.url_template:
            return self.url.format(**template_vars)
        return self.url

    def render_backend_url(self, **template_vars) -> str:
        """Render backend URL with template variables.

        Args:
            **template_vars: Variables to interpolate (e.g., instance_url="example.com")

        Returns:
            Rendered backend URL with variables replaced

        Raises:
            KeyError: If template variable missing

        Example:
            >>> settings.backend_url = "https://{instance_url}/oauth/token"
            >>> settings.render_backend_url(instance_url="example.com")
            'https://example.com/oauth/token'
        """
        if self.backend_url_template:
            return self.backend_url.format(**template_vars)
        return self.backend_url


class OAuth2WithRefreshSettings(OAuth2Settings):
    """OAuth2 with refresh token settings schema."""

    pass


class OAuth2WithRefreshRotatingSettings(OAuth2Settings):
    """OAuth2 with rotating refresh token settings schema."""

    pass


class ConfigClassAuthSettings(BaseAuthSettings):
    """Config class authentication settings schema."""

    pass


class OAuth1Settings(BaseAuthSettings):
    """OAuth1 authentication settings schema.

    OAuth1 uses a 3-legged flow with request tokens and access tokens.

    Attributes:
        integration_short_name: The integration short name
        request_token_url: URL to obtain temporary credentials (request token)
        authorization_url: URL to redirect user for authorization
        access_token_url: URL to exchange for access token
        consumer_key: OAuth consumer key (API key)
        consumer_secret: OAuth consumer secret
        scope: Optional scope (read, write, account, etc.)
        expiration: Optional token expiration (1hour, 1day, 30days, never)
    """

    integration_short_name: str
    request_token_url: str
    authorization_url: str
    access_token_url: str
    consumer_key: str
    consumer_secret: Optional[str] = None
    scope: Optional[str] = None
    expiration: Optional[str] = None

    @model_validator(mode="after")
    def validate_oauth1_fields(self):
        """Validate that OAuth1 integrations have required fields."""
        if not self.request_token_url:
            raise ValueError(
                f"OAuth1 integration {self.integration_short_name} missing 'request_token_url'"
            )
        if not self.authorization_url:
            raise ValueError(
                f"OAuth1 integration {self.integration_short_name} missing 'authorization_url'"
            )
        if not self.access_token_url:
            raise ValueError(
                f"OAuth1 integration {self.integration_short_name} missing 'access_token_url'"
            )
        if not self.consumer_key:
            raise ValueError(
                f"OAuth1 integration {self.integration_short_name} missing 'consumer_key'"
            )
        return self


class OAuth2AuthUrl(BaseModel):
    """OAuth2 authorization URL schema.

    Attributes:
    ----------
        url (str): The authorization URL.
    """

    url: str
