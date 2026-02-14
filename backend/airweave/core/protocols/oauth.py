"""Protocol for cross-cutting OAuth flow operations.

Used by source connections for OAuth browser/BYOC flows.
Future: destination OAuth, webhook registration flows.
"""

from typing import Any, Optional, Protocol


class OAuthFlowServiceProtocol(Protocol):
    """OAuth flow initiation and completion."""

    async def initiate_oauth2(
        self,
        short_name: str,
        payload: dict,
        organization_id: Any,
        redirect_url: Optional[str],
        byoc_client_id: Optional[str],
        byoc_client_secret: Optional[str],
        template_configs: Optional[dict],
        db: Any,
        uow: Any,
    ) -> Any:
        """Start OAuth2 browser flow: create init session, proxy URL, return auth URL.

        Returns OAuthInitResult.
        """
        ...

    async def initiate_oauth1(
        self,
        short_name: str,
        payload: dict,
        organization_id: Any,
        redirect_url: Optional[str],
        byoc_consumer_key: Optional[str],
        byoc_consumer_secret: Optional[str],
        db: Any,
        uow: Any,
    ) -> Any:
        """Start OAuth1 browser flow: request token, create init session, return auth URL.

        Returns OAuthInitResult.
        """
        ...

    async def complete_oauth2_callback(
        self,
        state: str,
        code: str,
        db: Any,
    ) -> Any:
        """Complete OAuth2 flow: look up init session, exchange code for tokens.

        Returns OAuthCompletionResult.
        Raises OAuthSessionNotFoundError, OAuthSessionExpiredError, OAuthTokenExchangeError.
        """
        ...

    async def complete_oauth1_callback(
        self,
        oauth_token: str,
        oauth_verifier: str,
        db: Any,
    ) -> Any:
        """Complete OAuth1 flow: look up init session, exchange verifier for access token.

        Returns OAuthCompletionResult.
        Raises OAuthSessionNotFoundError, OAuthTokenExchangeError.
        """
        ...
