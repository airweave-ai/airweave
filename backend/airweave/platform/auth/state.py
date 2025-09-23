# airweave/platform/auth/state.py
"""Create and verify compact HMAC-signed state tokens.

This module helps generate short-lived, tamper-evident "state" values that can
be round-tripped through third-party redirects (e.g., OAuth/OIDC) to mitigate
CSRF and replay. Tokens are shaped as:

    BASE64URL(JSON payload) "." BASE64URL(HMAC_SHA256(payload, STATE_SECRET))

The payload is augmented with:
- "ts": Unix timestamp (seconds) at creation time.
- "nonce": A URL-safe random string.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Dict

from airweave.core.config import settings


def _b64u(data: bytes) -> str:
    """Encode bytes as URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64u_dec(data: str) -> bytes:
    """Decode URL-safe base64, restoring any missing padding."""
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def make_state(payload: Dict[str, Any]) -> str:
    """Return a compact HMAC-signed state token for the given payload.

    Args:
        payload: JSON-serializable key/value pairs to embed in the token.

    Returns:
        A string token of the form "<b64url-body>.<b64url-signature>".

    Raises:
        TypeError: If the payload cannot be JSON-serialized.

    Notes:
        Anti-replay fields ("ts" and "nonce") are added to the payload.
    """
    # Add anti-replay bits
    payload = {
        **payload,
        "ts": int(time.time()),
        "nonce": secrets.token_urlsafe(16),
    }
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(settings.STATE_SECRET.encode(), body, hashlib.sha256).digest()
    return f"{_b64u(body)}.{_b64u(sig)}"


def verify_state(token: str, max_age_seconds: int = 10 * 60) -> Dict[str, Any]:
    """Validate and decode a state token.

    Args:
        token: The token produced by `make_state`.
        max_age_seconds: Maximum allowed token age in seconds (default 600).

    Returns:
        The decoded payload dictionary.

    Raises:
        ValueError: If the token is malformed, the signature is invalid, or the
            token is expired.
        json.JSONDecodeError: If the token body is not valid JSON.

    Security:
        Uses constant-time comparison for signature checks and enforces expiry.
    """
    try:
        body_b64, sig_b64 = token.split(".")
    except ValueError as err:
        # Make it explicit this comes from token splitting, not later logic.
        raise ValueError("Malformed state") from err

    body = _b64u_dec(body_b64)
    expected = hmac.new(settings.STATE_SECRET.encode(), body, hashlib.sha256).digest()
    got = _b64u_dec(sig_b64)

    if not hmac.compare_digest(expected, got):
        raise ValueError("Bad state signature")

    payload = json.loads(body.decode())

    if time.time() - payload.get("ts", 0) > max_age_seconds:
        raise ValueError("State expired")

    return payload
