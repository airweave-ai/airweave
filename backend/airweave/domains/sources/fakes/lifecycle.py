"""Fake source lifecycle service for testing."""

from __future__ import annotations

from typing import Any, Dict, Optional, Union
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.platform.sources._base import BaseSource


class FakeSourceLifecycleService:
    """Test implementation of SourceLifecycleServiceProtocol.

    Records calls for assertion and returns canned responses.

    Usage:
        fake = FakeSourceLifecycleService()

        # Seed a source that create() will return
        fake.seed_source(source_connection_id, mock_source_instance)

        result = await fake.create(db, source_connection_id, ctx)
        assert result is mock_source_instance

        # Assert validate() was called
        fake.set_validate_raises("bad_source", SourceValidationError(...))
    """

    def __init__(self) -> None:
        self._sources: dict[UUID, BaseSource] = {}
        self._validate_errors: dict[str, Exception] = {}
        self.create_calls: list[dict] = []
        self.validate_calls: list[dict] = []

    async def create(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
        *,
        access_token: Optional[str] = None,
    ) -> BaseSource:
        self.create_calls.append(
            {
                "source_connection_id": source_connection_id,
                "access_token": access_token,
            }
        )
        if source_connection_id not in self._sources:
            raise KeyError(
                f"FakeSourceLifecycleService: no source seeded for {source_connection_id}"
            )
        return self._sources[source_connection_id]

    async def validate(
        self,
        short_name: str,
        credentials: Union[dict, BaseModel, str],
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.validate_calls.append(
            {
                "short_name": short_name,
                "credentials": credentials,
                "config": config,
            }
        )
        if short_name in self._validate_errors:
            raise self._validate_errors[short_name]

    # Test helpers

    def seed_source(self, source_connection_id: UUID, source: BaseSource) -> None:
        """Pre-populate a source instance that create() will return."""
        self._sources[source_connection_id] = source

    def set_validate_raises(self, short_name: str, error: Exception) -> None:
        """Make validate() raise for a given short_name."""
        self._validate_errors[short_name] = error

    def clear(self) -> None:
        """Reset all state."""
        self._sources.clear()
        self._validate_errors.clear()
        self.create_calls.clear()
        self.validate_calls.clear()
