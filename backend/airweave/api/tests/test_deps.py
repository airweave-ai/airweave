"""Unit tests for dependency helpers in deps.py."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from airweave.api.deps import _resolve_organization_id
from airweave.core.shared_models import AuthMethod


def test_resolve_org_id_accepts_valid_uuid():
    valid_uuid = str(uuid4())
    result = _resolve_organization_id(
        x_organization_id=valid_uuid,
        user_context=None,
        auth_method=AuthMethod.AUTH0,
        auth_metadata={},
    )
    assert result == valid_uuid


@pytest.mark.parametrize(
    "malformed_value",
    [
        "'",
        "not-a-uuid",
        "1' OR '1'='1",
        "$(sleep 5)",
        "; DROP TABLE organizations;--",
        "",
    ],
)
def test_resolve_org_id_rejects_malformed_uuid(malformed_value):
    # Empty string is falsy so it won't enter the validation branch;
    # it should fall through and raise about missing org context instead.
    if malformed_value == "":
        with pytest.raises(HTTPException) as exc_info:
            _resolve_organization_id(
                x_organization_id=malformed_value,
                user_context=None,
                auth_method=AuthMethod.AUTH0,
                auth_metadata={},
            )
        assert exc_info.value.status_code == 400
        assert "Organization context required" in exc_info.value.detail
    else:
        with pytest.raises(HTTPException) as exc_info:
            _resolve_organization_id(
                x_organization_id=malformed_value,
                user_context=None,
                auth_method=AuthMethod.AUTH0,
                auth_metadata={},
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid organization ID format"


def test_resolve_org_id_falls_back_to_user_primary_org():
    user = MagicMock()
    user.primary_organization_id = uuid4()

    result = _resolve_organization_id(
        x_organization_id=None,
        user_context=user,
        auth_method=AuthMethod.AUTH0,
        auth_metadata={},
    )
    assert result == str(user.primary_organization_id)


def test_resolve_org_id_raises_when_no_org_available():
    user = MagicMock()
    user.primary_organization_id = None

    with pytest.raises(HTTPException) as exc_info:
        _resolve_organization_id(
            x_organization_id=None,
            user_context=user,
            auth_method=AuthMethod.AUTH0,
            auth_metadata={},
        )
    assert exc_info.value.status_code == 400
    assert "Organization context required" in exc_info.value.detail
