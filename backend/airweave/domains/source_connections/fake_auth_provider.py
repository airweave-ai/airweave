"""Fake auth provider service for testing."""

from typing import Any, Dict, List, Optional


class FakeAuthProviderService:
    """In-memory fake for AuthProviderServiceProtocol."""

    def __init__(self, should_raise: Optional[Exception] = None) -> None:
        self._should_raise = should_raise
        self._supported_providers: dict[str, List[str]] = {}
        self._validated_configs: dict[str, dict] = {}

    def _maybe_raise(self) -> None:
        if self._should_raise:
            raise self._should_raise

    def get_supported_providers_for_source(self, source_short_name: str) -> List[str]:
        self._maybe_raise()
        return self._supported_providers.get(source_short_name, [])

    async def validate_auth_provider_config(
        self, db: Any, auth_provider_short_name: str, auth_provider_config: Optional[Any]
    ) -> dict:
        self._maybe_raise()
        return self._validated_configs.get(auth_provider_short_name, {})

    def seed_supported(self, source: str, providers: List[str]) -> None:
        self._supported_providers[source] = providers

    def seed_validated_config(self, provider: str, config: dict) -> None:
        self._validated_configs[provider] = config

    def set_should_raise(self, exc: Optional[Exception]) -> None:
        self._should_raise = exc

    def clear(self) -> None:
        self._should_raise = None
        self._supported_providers.clear()
        self._validated_configs.clear()
