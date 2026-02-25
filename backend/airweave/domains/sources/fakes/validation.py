"""Fake source validation service for testing."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional

from fastapi import HTTPException
from pydantic import BaseModel

from airweave.api.context import ApiContext


class FakeSourceValidationService:
    """Test implementation of SourceValidationServiceProtocol.

    Returns canned results. Configure via seed methods.
    """

    def __init__(self) -> None:
        self._config_results: dict[str, dict[str, Any]] = {}
        self._auth_results: dict[str, BaseModel] = {}
        self._should_raise: Optional[Exception] = None
        self._calls: list[tuple[Any, ...]] = []

    def seed_config_result(self, short_name: str, result: dict[str, Any]) -> None:
        self._config_results[short_name] = result

    def seed_auth_result(self, short_name: str, result: BaseModel) -> None:
        self._auth_results[short_name] = result

    def set_error(self, error: Exception) -> None:
        self._should_raise = error

    def validate_config(
        self, short_name: str, config_fields: Mapping[str, Any] | None, ctx: ApiContext
    ) -> dict[str, Any]:
        self._calls.append(("validate_config", short_name, config_fields))
        if self._should_raise:
            raise self._should_raise
        if short_name not in self._config_results:
            raise HTTPException(status_code=404, detail=f"Source '{short_name}' not found")
        return self._config_results[short_name]

    def validate_auth_schema(self, short_name: str, auth_fields: dict[str, Any]) -> BaseModel:
        self._calls.append(("validate_auth_schema", short_name, auth_fields))
        if self._should_raise:
            raise self._should_raise
        if short_name not in self._auth_results:
            raise HTTPException(status_code=404, detail=f"Source '{short_name}' not found")
        return self._auth_results[short_name]
