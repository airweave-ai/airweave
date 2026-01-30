"""Pydantic schemas for OAuth 2.1 MCP authorization server."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# OAuth Client schemas
class OAuthClientBase(BaseModel):
    """Base schema for OAuth client."""

    client_id: str
    name: str
    redirect_uris: list[str]
    grant_types: list[str] = ["authorization_code"]
    client_type: str = "public"  # "public" or "confidential"


class OAuthClientCreate(OAuthClientBase):
    """Schema for creating OAuth client."""

    client_secret_hash: Optional[str] = None


class OAuthClientUpdate(BaseModel):
    """Schema for updating OAuth client."""

    name: Optional[str] = None
    redirect_uris: Optional[list[str]] = None
    grant_types: Optional[list[str]] = None


class OAuthClient(OAuthClientBase):
    """Schema for OAuth client response."""

    id: UUID
    created_at: datetime
    modified_at: datetime

    class Config:
        from_attributes = True


# OAuth Authorization Code schemas
class OAuthAuthorizationCodeBase(BaseModel):
    """Base schema for OAuth authorization code."""

    client_id: str
    user_id: UUID
    collection_id: UUID
    redirect_uri: str
    scope: str = "read:collection"


class OAuthAuthorizationCodeCreate(OAuthAuthorizationCodeBase):
    """Schema for creating OAuth authorization code."""

    code_hash: str
    organization_id: UUID
    code_challenge: Optional[str] = None
    code_challenge_method: Optional[str] = None
    expires_at: datetime


class OAuthAuthorizationCodeUpdate(BaseModel):
    """Schema for updating OAuth authorization code."""

    used_at: Optional[datetime] = None


class OAuthAuthorizationCode(OAuthAuthorizationCodeBase):
    """Schema for OAuth authorization code response."""

    id: UUID
    code_hash: str
    organization_id: UUID
    expires_at: datetime
    used_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# OAuth Access Token schemas
class OAuthAccessTokenBase(BaseModel):
    """Base schema for OAuth access token."""

    client_id: str
    user_id: UUID
    collection_id: UUID
    scope: str = "read:collection"


class OAuthAccessTokenCreate(OAuthAccessTokenBase):
    """Schema for creating OAuth access token."""

    token_hash: str
    organization_id: UUID
    expires_at: datetime


class OAuthAccessTokenUpdate(BaseModel):
    """Schema for updating OAuth access token."""

    revoked_at: Optional[datetime] = None


class OAuthAccessToken(OAuthAccessTokenBase):
    """Schema for OAuth access token response."""

    id: UUID
    token_hash: str
    organization_id: UUID
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# OAuth Request/Response schemas for API endpoints
class OAuthAuthorizationRequest(BaseModel):
    """OAuth authorization request parameters."""

    response_type: str = "code"
    client_id: str
    redirect_uri: str
    scope: str = "read:collection"
    state: str
    code_challenge: Optional[str] = None
    code_challenge_method: Optional[str] = None


class OAuthAuthorizationResponse(BaseModel):
    """OAuth authorization response."""

    code: str
    state: str


class OAuthTokenRequest(BaseModel):
    """OAuth token exchange request."""

    grant_type: str = "authorization_code"
    code: str
    redirect_uri: str
    client_id: str
    code_verifier: Optional[str] = None


class OAuthTokenResponse(BaseModel):
    """OAuth token response."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    scope: str
    collection_id: str
    collection_name: str


class OAuthErrorResponse(BaseModel):
    """OAuth error response."""

    error: str
    error_description: str


class OAuthServerMetadata(BaseModel):
    """OAuth 2.1 Authorization Server Metadata (RFC 8414)."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    revocation_endpoint: str
    grant_types_supported: list[str] = ["authorization_code"]
    response_types_supported: list[str] = ["code"]
    code_challenge_methods_supported: list[str] = ["S256"]
    token_endpoint_auth_methods_supported: list[str] = ["none"]
