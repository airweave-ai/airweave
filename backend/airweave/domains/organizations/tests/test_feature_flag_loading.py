"""Unit tests for resilient feature-flag loading in CRUDOrganization.

Covers the two methods that coerce DB strings → FeatureFlagEnum:
- _extract_enabled_features  (sync, reads org.__dict__)
- get_org_features           (async, queries DB)

Both must silently skip unknown flag values instead of crashing.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from airweave.core.shared_models import FeatureFlag as FeatureFlagEnum
from airweave.crud.crud_organization import CRUDOrganization
from airweave.models.organization import Organization


def _flag_row(flag: str, enabled: bool = True):
    """Build a stub feature_flag row."""
    row = MagicMock()
    row.flag = flag
    row.enabled = enabled
    return row


def _org_with_flags(flags: list) -> Organization:
    """Build a stub Organization with pre-loaded feature_flags in __dict__."""
    org = MagicMock(spec=Organization)
    org.__dict__["feature_flags"] = flags
    return org


def _mock_db(rows: list) -> AsyncMock:
    """Return an AsyncMock db whose execute() yields the given rows."""
    db = AsyncMock()
    scalars = MagicMock()
    scalars.all.return_value = rows
    result = MagicMock()
    result.scalars.return_value = scalars
    db.execute.return_value = result
    return db


@pytest.fixture
def crud():
    return CRUDOrganization()


# ── _extract_enabled_features ────────────────────────────────────────


class TestExtractEnabledFeatures:
    def test_known_flags_returned(self, crud):
        org = _org_with_flags([_flag_row("connect"), _flag_row("priority_support")])
        result = crud._extract_enabled_features(org)
        assert set(result) == {FeatureFlagEnum.CONNECT, FeatureFlagEnum.PRIORITY_SUPPORT}

    def test_disabled_flags_excluded(self, crud):
        org = _org_with_flags([
            _flag_row("connect", enabled=True),
            _flag_row("priority_support", enabled=False),
        ])
        result = crud._extract_enabled_features(org)
        assert result == [FeatureFlagEnum.CONNECT]

    def test_unknown_flag_skipped(self, crud):
        org = _org_with_flags([
            _flag_row("agentic_search"),
            _flag_row("connect"),
        ])
        result = crud._extract_enabled_features(org)
        assert result == [FeatureFlagEnum.CONNECT]

    def test_all_unknown_returns_empty(self, crud):
        org = _org_with_flags([_flag_row("totally_fake"), _flag_row("also_fake")])
        result = crud._extract_enabled_features(org)
        assert result == []

    def test_no_feature_flags_in_dict(self, crud):
        org = MagicMock(spec=Organization)
        result = crud._extract_enabled_features(org)
        assert result == []

    def test_empty_feature_flags_list(self, crud):
        org = _org_with_flags([])
        result = crud._extract_enabled_features(org)
        assert result == []


# ── get_org_features ─────────────────────────────────────────────────


class TestGetOrgFeatures:
    @pytest.mark.asyncio
    async def test_known_flags_returned(self, crud):
        db = _mock_db([_flag_row("connect"), _flag_row("priority_support")])
        result = await crud.get_org_features(db, organization_id=uuid4())
        assert set(result) == {FeatureFlagEnum.CONNECT, FeatureFlagEnum.PRIORITY_SUPPORT}

    @pytest.mark.asyncio
    async def test_unknown_flag_skipped(self, crud):
        db = _mock_db([_flag_row("agentic_search"), _flag_row("connect")])
        result = await crud.get_org_features(db, organization_id=uuid4())
        assert result == [FeatureFlagEnum.CONNECT]

    @pytest.mark.asyncio
    async def test_all_unknown_returns_empty(self, crud):
        db = _mock_db([_flag_row("ghost_flag")])
        result = await crud.get_org_features(db, organization_id=uuid4())
        assert result == []

    @pytest.mark.asyncio
    async def test_empty_db_returns_empty(self, crud):
        db = _mock_db([])
        result = await crud.get_org_features(db, organization_id=uuid4())
        assert result == []
