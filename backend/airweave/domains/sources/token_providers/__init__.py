"""Source auth provider implementations."""

from airweave.domains.sources.token_providers.auth_provider import AuthProviderTokenProvider
from airweave.domains.sources.token_providers.credential import DirectCredentialProvider
from airweave.domains.sources.token_providers.oauth import OAuthTokenProvider
from airweave.domains.sources.token_providers.protocol import (
    AuthProviderKind,
    SourceAuthProvider,
    TokenProviderProtocol,
)
from airweave.domains.sources.token_providers.static import StaticTokenProvider

__all__ = [
    "AuthProviderKind",
    "AuthProviderTokenProvider",
    "DirectCredentialProvider",
    "OAuthTokenProvider",
    "SourceAuthProvider",
    "StaticTokenProvider",
    "TokenProviderProtocol",
]
