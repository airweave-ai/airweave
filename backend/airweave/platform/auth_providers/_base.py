"""Base auth provider class."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set

from airweave.core.logging import logger
from airweave.platform.auth_providers.auth_result import AuthResult


class BaseAuthProvider(ABC):
    """Base class for all auth providers."""

    def __init__(self):
        """Initialize the base auth provider."""
        self._logger: Optional[Any] = None  # Store contextual logger as instance variable

    @property
    def logger(self):
        """Get the logger for this auth provider, falling back to default if not set."""
        if self._logger is not None:
            return self._logger
        # Fall back to default logger
        return logger

    def set_logger(self, logger) -> None:
        """Set a contextual logger for this auth provider."""
        self._logger = logger

    @classmethod
    @abstractmethod
    async def create(
        cls, credentials: Optional[Any] = None, config: Optional[Dict[str, Any]] = None
    ) -> "BaseAuthProvider":
        """Create a new auth provider instance.

        Args:
            credentials: Optional credentials for authenticated auth providers.
            config: Optional configuration parameters

        Returns:
            A configured auth provider instance
        """
        pass

    @abstractmethod
    async def get_creds_for_source(
        self,
        source_short_name: str,
        source_auth_config_fields: List[str],
        optional_fields: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Get credentials for a source.

        Args:
            source_short_name: The short name of the source to get credentials for
            source_auth_config_fields: The fields required for the source auth config
            optional_fields: Fields that can be skipped if the provider doesn't have them
        """
        pass

    @abstractmethod
    async def validate(self) -> bool:
        """Validate that the auth provider connection works.

        Returns:
            True if the connection is valid, False otherwise

        Raises:
            HTTPException: If validation fails with detailed error message
        """
        pass

    async def get_config_for_source(
        self,
        source_short_name: str,
        source_config_field_mappings: Dict[str, str],
    ) -> Dict[str, Any]:
        """Extract config fields from the auth provider's credential response.

        Override in providers that have access to extra metadata (e.g., instance_url).

        Args:
            source_short_name: The short name of the source
            source_config_field_mappings: Mapping of config_field_name -> provider_field_name

        Returns:
            Dict of config field values extracted from the provider response
        """
        return {}

    async def get_auth_result(
        self,
        source_short_name: str,
        source_auth_config_fields: List[str],
        optional_fields: Optional[Set[str]] = None,
        source_config_field_mappings: Optional[Dict[str, str]] = None,
    ) -> AuthResult:
        """Get auth result with explicit mode (direct vs proxy).

        Default implementation calls get_creds_for_source and returns direct mode.
        Subclasses can override to return proxy mode when needed.

        Args:
            source_short_name: The short name of the source
            source_auth_config_fields: The fields required for the source auth config
            optional_fields: Fields that can be skipped if the provider doesn't have them
            source_config_field_mappings: Mapping of config fields extractable from auth response

        Returns:
            AuthResult with explicit mode, credentials, and optional source config
        """
        credentials = await self.get_creds_for_source(
            source_short_name, source_auth_config_fields, optional_fields
        )

        source_config = {}
        if source_config_field_mappings:
            source_config = await self.get_config_for_source(
                source_short_name, source_config_field_mappings
            )

        result = AuthResult.direct(credentials)
        result.source_config = source_config or None
        return result
