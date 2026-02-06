"""Auth result types for explicit auth mode communication."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class AuthProviderMode(Enum):
    """Explicit auth mode enumeration."""

    DIRECT = "direct"  # Use credentials directly
    PROXY = "proxy"  # Route through proxy (e.g., Pipedream)


@dataclass
class AuthResult:
    """Result of auth provider credential fetch.

    This makes explicit whether to use credentials directly or via proxy.
    source_config carries non-secret config fields (e.g., instance_url) that
    the auth provider extracted alongside credentials.
    """

    mode: AuthProviderMode
    credentials: Optional[Any] = None  # Actual credentials (if DIRECT mode)
    proxy_config: Optional[Dict[str, Any]] = None  # Config for proxy (if PROXY mode)
    source_config: Optional[Dict[str, Any]] = None  # Config fields from auth provider response

    @classmethod
    def direct(cls, credentials: Any) -> "AuthResult":
        """Create a direct auth result with credentials."""
        return cls(mode=AuthProviderMode.DIRECT, credentials=credentials)

    @classmethod
    def proxy(cls, config: Optional[Dict[str, Any]] = None) -> "AuthResult":
        """Create a proxy auth result."""
        return cls(mode=AuthProviderMode.PROXY, proxy_config=config or {})

    @property
    def requires_proxy(self) -> bool:
        """Check if proxy is required."""
        return self.mode == AuthProviderMode.PROXY
