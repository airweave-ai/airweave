"""Unit tests for SourceValidationService."""

from typing import Any

import pytest
from fastapi import HTTPException
from pydantic import BaseModel

from airweave.domains.sources.fakes.registry import FakeSourceRegistry
from airweave.domains.sources.tests.conftest import _make_ctx, _make_entry
from airweave.domains.sources.validation import SourceValidationService


class _ConfigSchema(BaseModel):
    required_key: str


class _AuthSchema(BaseModel):
    token: str


def _build_service() -> SourceValidationService:
    registry = FakeSourceRegistry()
    entry = _make_entry("github", "GitHub").model_copy(
        update={"config_ref": _ConfigSchema, "auth_config_ref": _AuthSchema}
    )
    registry.seed(entry)
    return SourceValidationService(source_registry=registry)


def test_validate_config_non_mapping_fails_loud():
    svc = _build_service()
    with pytest.raises(TypeError, match="mapping-like"):
        svc.validate_config("github", [{"key": "foo", "value": "bar"}], _make_ctx())  # type: ignore[arg-type]


def test_validate_config_validation_error_maps_to_422():
    svc = _build_service()
    with pytest.raises(HTTPException) as exc_info:
        svc.validate_config("github", {"wrong": "value"}, _make_ctx())
    assert exc_info.value.status_code == 422
    assert "Invalid config fields" in str(exc_info.value.detail)


def test_validate_auth_schema_validation_error_maps_to_422():
    svc = _build_service()
    with pytest.raises(HTTPException) as exc_info:
        svc.validate_auth_schema("github", {"wrong": "value"})
    assert exc_info.value.status_code == 422
    assert "Invalid auth fields" in str(exc_info.value.detail)


def test_validate_auth_schema_returns_model():
    svc = _build_service()
    validated = svc.validate_auth_schema("github", {"token": "secret"})
    assert isinstance(validated, BaseModel)
    assert validated.model_dump() == {"token": "secret"}


def test_validate_config_passthrough_when_no_schema():
    registry = FakeSourceRegistry()
    entry = _make_entry("slack", "Slack").model_copy(update={"config_ref": None})
    registry.seed(entry)

    svc = SourceValidationService(source_registry=registry)
    payload: dict[str, Any] = {"x": 1}
    assert svc.validate_config("slack", payload, _make_ctx()) == payload
