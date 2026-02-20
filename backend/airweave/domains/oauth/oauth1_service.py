"""OAuth1 authentication service for integrations that use OAuth 1.0 protocol.

This service handles the 3-legged OAuth1 flow:
1. Obtain temporary credentials (request token)
2. Redirect user for authorization
3. Exchange for access token

Reference: RFC 5849 - The OAuth 1.0 Protocol
"""

import base64
import hashlib
import hmac
import secrets
import time
from typing import Optional
from urllib.parse import parse_qsl, quote, urlencode

import httpx
from fastapi import HTTPException

from airweave.core.logging import ContextualLogger
from airweave.domains.oauth.protocols import OAuth1ServiceProtocol
from airweave.domains.oauth.types import OAuth1TokenResponse


class OAuth1Service(OAuth1ServiceProtocol):
    """Service for handling OAuth1 authentication flows."""

    def _generate_nonce(self) -> str:
        """Generate a cryptographically secure random nonce."""
        return secrets.token_urlsafe(32)

    def _get_timestamp(self) -> str:
        """Get current Unix timestamp as string."""
        return str(int(time.time()))

    def _percent_encode(self, value: str) -> str:
        """Percent-encode a value according to RFC 3986.

        Encodes all characters except unreserved: A-Z, a-z, 0-9, -, ., _, ~
        """
        return quote(str(value), safe="~")

    def _build_signature_base_string(self, method: str, url: str, params: dict) -> str:
        """Build the signature base string per RFC 5849.

        Format: HTTP_METHOD&URL&NORMALIZED_PARAMS
        """
        sorted_params = sorted(params.items())
        param_str = "&".join(
            f"{self._percent_encode(k)}={self._percent_encode(v)}" for k, v in sorted_params
        )

        parts = [
            method.upper(),
            self._percent_encode(url),
            self._percent_encode(param_str),
        ]
        return "&".join(parts)

    def _sign_hmac_sha1(
        self, base_string: str, consumer_secret: str, token_secret: str = ""
    ) -> str:
        """Sign the base string using HMAC-SHA1.

        Signing key: percent_encode(consumer_secret)&percent_encode(token_secret)
        """
        encoded_consumer = self._percent_encode(consumer_secret)
        encoded_token = self._percent_encode(token_secret)
        key = f"{encoded_consumer}&{encoded_token}"
        key_bytes = key.encode("utf-8")
        base_bytes = base_string.encode("utf-8")

        signature_bytes = hmac.new(key_bytes, base_bytes, hashlib.sha1).digest()
        return base64.b64encode(signature_bytes).decode("utf-8")

    def _build_authorization_header(self, params: dict) -> str:
        """Build OAuth1 Authorization header.

        Format: OAuth oauth_consumer_key="...", oauth_nonce="...", ...
        """
        sorted_items = sorted(params.items())
        param_strings = [
            f'{self._percent_encode(k)}="{self._percent_encode(v)}"' for k, v in sorted_items
        ]
        return "OAuth " + ", ".join(param_strings)

    async def get_request_token(
        self,
        *,
        request_token_url: str,
        consumer_key: str,
        consumer_secret: str,
        callback_url: str,
        logger: ContextualLogger,
    ) -> OAuth1TokenResponse:
        """Obtain temporary credentials (request token) from OAuth1 provider.

        Args:
            request_token_url: Provider's request token endpoint
            consumer_key: Client identifier (API key)
            consumer_secret: Client secret
            callback_url: Callback URL for OAuth flow
            logger: Logger for debugging

        Returns:
            OAuth1TokenResponse with temporary credentials

        Raises:
            HTTPException: If request token retrieval fails
        """
        oauth_params = {
            "oauth_consumer_key": consumer_key,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": self._get_timestamp(),
            "oauth_nonce": self._generate_nonce(),
            "oauth_version": "1.0",
            "oauth_callback": callback_url,
        }

        base_string = self._build_signature_base_string("POST", request_token_url, oauth_params)

        signature = self._sign_hmac_sha1(base_string, consumer_secret, "")
        oauth_params["oauth_signature"] = signature

        auth_header = self._build_authorization_header(oauth_params)

        logger.info(f"Requesting OAuth1 temporary credentials from {request_token_url}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    request_token_url,
                    headers={
                        "Authorization": auth_header,
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
                response.raise_for_status()

            response_params = dict(parse_qsl(response.text))

            if "oauth_token" not in response_params or "oauth_token_secret" not in response_params:
                logger.error(f"Invalid response from OAuth1 provider: {response.text}")
                raise HTTPException(status_code=400, detail="Invalid response from OAuth1 provider")

            logger.info("Successfully obtained OAuth1 temporary credentials")

            return OAuth1TokenResponse(
                oauth_token=response_params["oauth_token"],
                oauth_token_secret=response_params["oauth_token_secret"],
                **{
                    k: v
                    for k, v in response_params.items()
                    if k not in ["oauth_token", "oauth_token_secret"]
                },
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error obtaining request token: {e.response.status_code} - {e.response.text}"
            )
            raise HTTPException(
                status_code=400, detail=f"Failed to obtain request token: {e.response.text}"
            ) from e
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error(f"Unexpected error obtaining request token: {str(e)}")
            raise HTTPException(
                status_code=400, detail=f"Failed to obtain request token: {str(e)}"
            ) from e

    async def exchange_token(
        self,
        *,
        access_token_url: str,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
        oauth_verifier: str,
        logger: ContextualLogger,
    ) -> OAuth1TokenResponse:
        """Exchange temporary credentials for access token credentials.

        Args:
            access_token_url: Provider's access token endpoint
            consumer_key: Client identifier (API key)
            consumer_secret: Client secret
            oauth_token: Temporary token from step 1
            oauth_token_secret: Temporary token secret from step 1
            oauth_verifier: Verification code from user authorization
            logger: Logger for debugging

        Returns:
            OAuth1TokenResponse with access token credentials

        Raises:
            HTTPException: If token exchange fails
        """
        oauth_params = {
            "oauth_consumer_key": consumer_key,
            "oauth_token": oauth_token,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": self._get_timestamp(),
            "oauth_nonce": self._generate_nonce(),
            "oauth_version": "1.0",
            "oauth_verifier": oauth_verifier,
        }

        base_string = self._build_signature_base_string("POST", access_token_url, oauth_params)

        signature = self._sign_hmac_sha1(base_string, consumer_secret, oauth_token_secret)
        oauth_params["oauth_signature"] = signature

        auth_header = self._build_authorization_header(oauth_params)

        logger.info(
            f"Exchanging OAuth1 temporary credentials for access token at {access_token_url}"
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    access_token_url,
                    headers={
                        "Authorization": auth_header,
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
                response.raise_for_status()

            response_params = dict(parse_qsl(response.text))

            if "oauth_token" not in response_params or "oauth_token_secret" not in response_params:
                logger.error(f"Invalid access token response: {response.text}")
                raise HTTPException(status_code=400, detail="Invalid access token response")

            logger.info("Successfully obtained OAuth1 access token")

            return OAuth1TokenResponse(
                oauth_token=response_params["oauth_token"],
                oauth_token_secret=response_params["oauth_token_secret"],
                **{
                    k: v
                    for k, v in response_params.items()
                    if k not in ["oauth_token", "oauth_token_secret"]
                },
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error exchanging token: {e.response.status_code} - {e.response.text}"
            )
            raise HTTPException(
                status_code=400, detail=f"Failed to exchange OAuth1 token: {e.response.text}"
            ) from e
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error(f"Unexpected error exchanging token: {str(e)}")
            raise HTTPException(
                status_code=400, detail=f"Failed to exchange OAuth1 token: {str(e)}"
            ) from e

    def build_authorization_url(
        self,
        *,
        authorization_url: str,
        oauth_token: str,
        app_name: Optional[str] = None,
        scope: Optional[str] = None,
        expiration: Optional[str] = None,
    ) -> str:
        """Build the authorization URL for user consent (step 2 of OAuth1 flow).

        Args:
            authorization_url: Provider's authorization endpoint
            oauth_token: Temporary token from step 1
            app_name: Optional app name to display
            scope: Optional scope (read, write, account, etc.)
            expiration: Optional expiration (1hour, 1day, 30days, never)

        Returns:
            Complete authorization URL for user redirect
        """
        params = {"oauth_token": oauth_token}

        if app_name:
            params["name"] = app_name
        if scope:
            params["scope"] = scope
        if expiration:
            params["expiration"] = expiration

        return f"{authorization_url}?{urlencode(params)}"
