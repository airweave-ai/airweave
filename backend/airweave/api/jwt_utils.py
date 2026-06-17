"""Shared JWT claim extraction for API endpoints."""

from typing import Optional

from fastapi import Request
from jose import jwt as jose_jwt

from airweave.core.config import settings
from airweave.core.logging import logger


def extract_claims(request: Request) -> Optional[dict]:
    """Extract unverified JWT claims from the Bearer token, or None."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        return jose_jwt.get_unverified_claims(auth_header[7:])
    except Exception:
        logger.debug("Failed to parse JWT claims from request")
        return None


def extract_sid(request: Request) -> Optional[str]:
    """Extract the Auth0 session ID from the JWT in the request."""
    claims = extract_claims(request)
    if claims is None:
        return None
    return claims.get(settings.AUTH0_SID_CLAIM_KEY)
