"""Value types for the OAuth domain.

These live in a separate module to avoid circular imports between
service implementations and protocol definitions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class OAuth1TokenResponse:
    """Response from OAuth1 token exchange."""

    def __init__(self, oauth_token: str, oauth_token_secret: str, **kwargs: str) -> None:
        """Initialize with token, secret, and any additional provider params."""
        self.oauth_token = oauth_token
        self.oauth_token_secret = oauth_token_secret
        self.additional_params = kwargs


@dataclass(slots=True)
class OAuthBrowserInitiationResult:
    """Normalized browser-flow initiation output for create-service orchestration."""

    provider_auth_url: str
    client_id: Optional[str]
    client_secret: Optional[str]
    oauth_client_mode: str
    additional_overrides: Dict[str, Any] = field(default_factory=dict)
