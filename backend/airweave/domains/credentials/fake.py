"""Fake credential service for testing."""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from airweave.schemas.source_connection import AuthenticationMethod


class FakeCredentialService:
    """Test implementation of CredentialServiceProtocol.

    By default all validations pass and create/update succeed.
    Set should_raise to inject specific exceptions for error-path testing.

    Usage:
        fake = FakeCredentialService()
        await fake.validate_auth_fields("slack", {"api_key": "xoxb-..."})

        # Test error path:
        fake = FakeCredentialService(
            should_raise=InvalidCredentialsError("bad token")
        )
    """

    def __init__(self, should_raise: Optional[Exception] = None) -> None:
        self._should_raise = should_raise
        self._created_credentials: list[dict] = []
        self._updated_credentials: list[dict] = []

    def _maybe_raise(self) -> None:
        if self._should_raise is not None:
            raise self._should_raise

    async def validate_auth_fields(self, short_name: str, auth_fields: dict) -> Any:
        self._maybe_raise()
        return auth_fields

    async def validate_config_fields(
        self, short_name: str, config_fields: Any, enabled_features: list
    ) -> dict:
        self._maybe_raise()
        if isinstance(config_fields, dict):
            return config_fields
        if hasattr(config_fields, "model_dump"):
            return config_fields.model_dump()
        return {}

    async def validate_direct_auth(
        self, short_name: str, auth_config: Any, config_fields: Any
    ) -> None:
        self._maybe_raise()

    async def validate_oauth_token(
        self, short_name: str, access_token: str, config_fields: Any
    ) -> None:
        self._maybe_raise()

    async def create_credential(
        self,
        source_short_name: str,
        source_name: str,
        auth_fields: dict,
        organization_id: Any,
        auth_method: AuthenticationMethod,
        oauth_type: Optional[str],
        auth_config_class: Optional[str],
        db: Any,
        uow: Any,
    ) -> Any:
        self._maybe_raise()
        cred = {
            "id": uuid4(),
            "source_short_name": source_short_name,
            "auth_method": auth_method,
        }
        self._created_credentials.append(cred)
        return type("FakeCredential", (), cred)()

    async def update_credential(
        self,
        credential_id: Any,
        auth_fields: dict,
        short_name: str,
        db: Any,
        uow: Any,
    ) -> None:
        self._maybe_raise()
        self._updated_credentials.append({"credential_id": credential_id, "short_name": short_name})

    # Test helpers

    def set_should_raise(self, exc: Optional[Exception]) -> None:
        """Configure the exception to raise on next call."""
        self._should_raise = exc

    def clear(self) -> None:
        """Reset all state."""
        self._should_raise = None
        self._created_credentials.clear()
        self._updated_credentials.clear()
