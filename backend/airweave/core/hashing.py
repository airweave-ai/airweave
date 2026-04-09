"""Pure-utility HMAC-SHA256 hashing for API keys."""

import hashlib
import hmac

from airweave.core.config import settings


def hash_api_key(key: str) -> str:
    """HMAC-SHA256 hash of an API key, keyed by ENCRYPTION_KEY.

    Keys are 256-bit entropy (secrets.token_urlsafe(32)); the 8-char
    key_prefix leaks ~48 bits, leaving ~208 bits — brute-force is
    infeasible through any hash.  HMAC keying adds defense-in-depth
    so stored hashes are useless without ENCRYPTION_KEY.
    """
    return hmac.new(
        settings.ENCRYPTION_KEY.encode(),
        key.encode(),
        hashlib.sha256,
    ).hexdigest()
