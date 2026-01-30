"""OAuth 2.1 authorization server service for MCP."""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import ContextualLogger
from airweave.platform.auth.oauth2_service import OAuth2Service


class OAuthServiceError(Exception):
    """Base exception for OAuth service errors."""

    pass


class OAuthService:
    """OAuth 2.1 authorization server service for MCP clients.

    This service handles the OAuth flow for MCP clients (Claude Desktop, Cursor)
    to access Airweave collections. It leverages existing PKCE utilities from
    the platform OAuth2Service.
    """

    # Token configuration
    AUTHORIZATION_CODE_TTL_SECONDS = 600  # 10 minutes
    ACCESS_TOKEN_TTL_SECONDS = 3600  # 1 hour
    TOKEN_PREFIX = "oat_"  # OAuth Access Token prefix

    @staticmethod
    async def create_authorization_code(
        db: AsyncSession,
        *,
        user_id: UUID,
        organization_id: UUID,
        client_id: str,
        collection_id: UUID,
        redirect_uri: str,
        scope: str,
        state: str,
        code_challenge: Optional[str] = None,
        code_challenge_method: Optional[str] = None,
        logger: Optional[ContextualLogger] = None,
    ) -> Tuple[str, str]:
        """Create an authorization code for OAuth flow.

        Args:
            db: Database session
            user_id: User granting authorization
            organization_id: Organization ID
            client_id: OAuth client ID
            collection_id: Collection being granted access to
            redirect_uri: URI to redirect to after authorization
            scope: OAuth scope (e.g., "read:collection")
            state: CSRF protection state parameter
            code_challenge: PKCE code challenge (S256 hash)
            code_challenge_method: PKCE method ("S256")
            logger: Optional logger

        Returns:
            Tuple of (authorization_code, redirect_url_with_code)

        Raises:
            NotFoundException: If client or collection not found
        """
        # Validate client exists
        client = await crud.oauth_client.get_by_client_id(db, client_id=client_id)

        # Validate redirect URI
        if not crud.oauth_client.validate_redirect_uri(client, redirect_uri):
            raise OAuthServiceError(f"Invalid redirect_uri for client {client_id}")

        # Validate collection exists and user has access
        collection = await crud.collection.get(db, id=collection_id)
        if not collection:
            raise NotFoundException(f"Collection {collection_id} not found")

        # Generate authorization code
        code = OAuthService._generate_token()
        code_hash = OAuthService.hash_token(code)

        # Create authorization code in database
        expires_at = utc_now_naive() + timedelta(seconds=OAuthService.AUTHORIZATION_CODE_TTL_SECONDS)

        auth_code_create = schemas.OAuthAuthorizationCodeCreate(
            code_hash=code_hash,
            client_id=client_id,
            user_id=user_id,
            organization_id=organization_id,
            collection_id=collection_id,
            redirect_uri=redirect_uri,
            scope=scope,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            expires_at=expires_at,
        )

        await crud.oauth_authorization_code.create(db, obj_in=auth_code_create)

        if logger:
            logger.info(
                f"Created authorization code for user {user_id}, client {client_id}, "
                f"collection {collection_id}"
            )

        # Build redirect URL with code and state
        separator = "&" if "?" in redirect_uri else "?"
        redirect_url = f"{redirect_uri}{separator}code={code}&state={state}"

        return code, redirect_url

    @staticmethod
    async def exchange_code_for_token(
        db: AsyncSession,
        *,
        code: str,
        client_id: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None,
        logger: Optional[ContextualLogger] = None,
    ) -> schemas.OAuthTokenResponse:
        """Exchange authorization code for access token.

        Args:
            db: Database session
            code: Authorization code
            client_id: OAuth client ID
            redirect_uri: Must match the one used in authorization request
            code_verifier: PKCE code verifier
            logger: Optional logger

        Returns:
            OAuth token response with access token and collection info

        Raises:
            OAuthServiceError: If code is invalid, expired, or already used
        """
        # Hash the code to look it up
        code_hash = OAuthService.hash_token(code)

        # Retrieve authorization code
        auth_code = await crud.oauth_authorization_code.get_by_code(db, code_hash=code_hash)

        if not auth_code:
            raise OAuthServiceError("Invalid authorization code")

        # Validate code hasn't been used
        if auth_code.used_at:
            raise OAuthServiceError("Authorization code has already been used")

        # Validate code hasn't expired
        if auth_code.expires_at < utc_now_naive():
            raise OAuthServiceError("Authorization code has expired")

        # Validate client_id matches
        if auth_code.client_id != client_id:
            raise OAuthServiceError("Client ID mismatch")

        # Validate redirect_uri matches
        if auth_code.redirect_uri != redirect_uri:
            raise OAuthServiceError("Redirect URI mismatch")

        # Verify PKCE if present
        if auth_code.code_challenge:
            if not code_verifier:
                raise OAuthServiceError("PKCE code_verifier required but not provided")

            if not OAuth2Service._verify_pkce_challenge(code_verifier, auth_code.code_challenge):
                raise OAuthServiceError("PKCE verification failed")

        # Mark code as used
        await crud.oauth_authorization_code.mark_as_used(db, code_id=auth_code.id)

        # Generate access token
        access_token = OAuthService._generate_token(prefix=OAuthService.TOKEN_PREFIX)
        token_hash = OAuthService.hash_token(access_token)

        # Create access token in database
        expires_at = utc_now_naive() + timedelta(seconds=OAuthService.ACCESS_TOKEN_TTL_SECONDS)

        token_create = schemas.OAuthAccessTokenCreate(
            token_hash=token_hash,
            client_id=client_id,
            user_id=auth_code.user_id,
            organization_id=auth_code.organization_id,
            collection_id=auth_code.collection_id,
            scope=auth_code.scope,
            expires_at=expires_at,
        )

        await crud.oauth_access_token.create(db, obj_in=token_create)

        # Get collection name
        collection = await crud.collection.get(db, id=auth_code.collection_id)

        if logger:
            logger.info(
                f"Issued access token for user {auth_code.user_id}, "
                f"client {client_id}, collection {auth_code.collection_id}"
            )

        return schemas.OAuthTokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=OAuthService.ACCESS_TOKEN_TTL_SECONDS,
            scope=auth_code.scope,
            collection_id=str(auth_code.collection_id),
            collection_name=collection.name if collection else "unknown",
        )

    @staticmethod
    async def validate_access_token(
        db: AsyncSession, *, token: str, logger: Optional[ContextualLogger] = None
    ) -> Tuple[UUID, UUID, UUID]:
        """Validate an OAuth access token.

        Args:
            db: Database session
            token: Access token to validate
            logger: Optional logger

        Returns:
            Tuple of (user_id, organization_id, collection_id)

        Raises:
            OAuthServiceError: If token is invalid, expired, or revoked
        """
        # Hash token to look it up
        token_hash = OAuthService.hash_token(token)

        # Retrieve token from database
        access_token = await crud.oauth_access_token.get_by_token(db, token_hash=token_hash)

        if not access_token:
            raise OAuthServiceError("Invalid access token")

        # Check if token has been revoked
        if access_token.revoked_at:
            raise OAuthServiceError("Access token has been revoked")

        # Check if token has expired
        if access_token.expires_at < utc_now_naive():
            raise OAuthServiceError("Access token has expired")

        if logger:
            logger.debug(
                f"Validated access token for user {access_token.user_id}, "
                f"collection {access_token.collection_id}"
            )

        return access_token.user_id, access_token.organization_id, access_token.collection_id

    @staticmethod
    async def revoke_access_token(
        db: AsyncSession, *, token: str, logger: Optional[ContextualLogger] = None
    ) -> None:
        """Revoke an OAuth access token.

        Args:
            db: Database session
            token: Access token to revoke
            logger: Optional logger

        Raises:
            OAuthServiceError: If token not found
        """
        token_hash = OAuthService.hash_token(token)
        access_token = await crud.oauth_access_token.get_by_token(db, token_hash=token_hash)

        if not access_token:
            raise OAuthServiceError("Token not found")

        await crud.oauth_access_token.revoke_token(db, token_id=access_token.id)

        if logger:
            logger.info(f"Revoked access token {access_token.id}")

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token using SHA256.

        Args:
            token: Token to hash

        Returns:
            Hex digest of SHA256 hash
        """
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def _generate_token(length: int = 32, prefix: str = "") -> str:
        """Generate a cryptographically secure random token.

        Args:
            length: Number of random bytes (token will be longer due to encoding)
            prefix: Optional prefix for the token

        Returns:
            URL-safe base64 encoded token with optional prefix
        """
        token = secrets.token_urlsafe(length)
        return f"{prefix}{token}" if prefix else token

    @staticmethod
    def _verify_pkce_challenge(verifier: str, challenge: str) -> bool:
        """Verify PKCE code verifier matches code challenge.

        Reuses the logic from platform OAuth2Service.

        Args:
            verifier: Code verifier from token request
            challenge: Code challenge from authorization request

        Returns:
            True if verifier matches challenge, False otherwise
        """
        # Leverage existing PKCE verification from OAuth2Service
        import base64

        # Compute SHA256 hash of verifier
        verifier_bytes = verifier.encode("ascii")
        sha256_hash = hashlib.sha256(verifier_bytes).digest()

        # Base64 URL-encode the hash (without padding)
        computed_challenge = base64.urlsafe_b64encode(sha256_hash).decode("ascii").rstrip("=")

        return computed_challenge == challenge
