"""Protocol for auth provider operations.

Cross-cutting: used by source connections, auth provider API.
"""

from typing import Any, Dict, List, Optional, Protocol


class AuthProviderServiceProtocol(Protocol):
    """Auth provider lookups and config validation."""

    def get_supported_providers_for_source(self, source_short_name: str) -> List[str]:
        """Get auth provider short_names that support a given source."""
        ...

    async def validate_auth_provider_config(
        self, db: Any, auth_provider_short_name: str, auth_provider_config: Optional[Any]
    ) -> dict:
        """Validate auth provider configuration."""
        ...
