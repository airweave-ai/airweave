"""Auth result types for auth provider credential fetch."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AuthResult:
    """Result of auth provider credential fetch.

    Credentials are always used directly by the source (no proxy mode).
    source_config carries non-secret config fields (e.g., instance_url)
    that the auth provider extracted alongside credentials.
    """

    credentials: Optional[Dict[str, Any]] = None
    source_config: Optional[Dict[str, Any]] = None

    @classmethod
    def direct(cls, credentials: Dict[str, Any]) -> "AuthResult":
        """Create an auth result with credentials."""
        return cls(credentials=credentials)
