"""DirectCredentialProvider — typed structured credentials for sources.

Used by sources that need more than a string token: NTLM username/password,
client_credentials (client_id + client_secret), database connection params, etc.

Implements ``SourceAuthProvider`` but NOT ``TokenProviderProtocol`` — calling
``get_token()`` on this provider is a type error, not a runtime surprise.
"""

from typing import Generic, TypeVar

from airweave.domains.sources.token_providers.protocol import AuthProviderKind, SourceAuthProvider

T = TypeVar("T")


class DirectCredentialProvider(SourceAuthProvider, Generic[T]):
    """Provides typed structured credentials to a source.

    The generic parameter ``T`` is the source's auth config Pydantic model
    (e.g., ``SharePoint2019V2AuthConfig``, ``ShopifyAuthConfig``).

    ``supports_refresh`` is always ``False`` — structured credentials are
    static for the lifetime of a sync.
    """

    def __init__(self, credentials: T, *, source_short_name: str = "") -> None:
        """Initialize with typed credentials."""
        self._credentials = credentials
        self._source_short_name = source_short_name

    @property
    def credentials(self) -> T:
        """The typed credential object."""
        return self._credentials

    @property
    def provider_kind(self) -> AuthProviderKind:
        """Discriminator for this auth provider type."""
        return AuthProviderKind.CREDENTIAL

    @property
    def supports_refresh(self) -> bool:
        """Structured credentials are static — no refresh."""
        return False
