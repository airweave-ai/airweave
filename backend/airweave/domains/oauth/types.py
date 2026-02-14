"""OAuth flow result types."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID


@dataclass(frozen=True)
class OAuthInitResult:
    """Result of initiating an OAuth flow.

    Returned by initiate_oauth2/initiate_oauth1. The calling domain
    uses auth_url and init_session_id to set up the shell connection.
    """

    auth_url: str
    proxy_url: str
    proxy_expiry: datetime
    init_session_id: UUID
    redirect_session_id: UUID


@dataclass(frozen=True)
class OAuthCompletionResult:
    """Result of completing an OAuth callback.

    Returned by complete_oauth2_callback/complete_oauth1_callback.
    The calling domain uses token_response + original_payload to
    finish creating the connection (credential, sync, etc.).
    """

    token_response: Any
    init_session: Any  # ConnectionInitSession ORM object
    original_payload: dict
    overrides: dict
    short_name: str
    organization_id: UUID
