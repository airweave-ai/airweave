"""Unit tests for SourceService.

Table-driven tests using FakeSourceRegistry, mock Settings, and minimal ApiContext.
No database, no real sources loaded.
"""

from dataclasses import dataclass, field

import pytest

from airweave.core.shared_models import FeatureFlag
from airweave.domains.sources.fake import FakeSourceRegistry
from airweave.domains.sources.service import SourceService
from airweave.domains.sources.tests.conftest import _make_ctx, _make_entry, _make_settings


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------


@dataclass
class GetCase:
    desc: str
    short_name: str
    seed: bool = True  # whether to seed the entry into the registry
    feature_flag: str | None = None
    enabled_features: list = field(default_factory=list)
    expect_short_name: str | None = None  # None = expect KeyError


GET_CASES = [
    GetCase(
        desc="returns known source",
        short_name="slack",
        expect_short_name="slack",
    ),
    GetCase(
        desc="unknown source raises KeyError",
        short_name="nonexistent",
        seed=False,
    ),
    GetCase(
        desc="flagged source hidden without flag",
        short_name="gated",
        feature_flag="sharepoint_2019_v2",
    ),
    GetCase(
        desc="flagged source visible with flag",
        short_name="gated",
        feature_flag="sharepoint_2019_v2",
        enabled_features=[FeatureFlag.SHAREPOINT_2019_V2],
        expect_short_name="gated",
    ),
    GetCase(
        desc="invalid feature flag fails open",
        short_name="weird",
        feature_flag="totally_invalid_flag",
        expect_short_name="weird",
    ),
]


@pytest.mark.parametrize("case", GET_CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_get(case: GetCase):
    registry = FakeSourceRegistry()
    if case.seed:
        registry.seed(_make_entry(case.short_name, case.short_name.title(), feature_flag=case.feature_flag))
    service = SourceService(source_registry=registry, settings=_make_settings())
    ctx = _make_ctx(enabled_features=case.enabled_features)

    if case.expect_short_name is None:
        with pytest.raises(KeyError):
            await service.get(case.short_name, ctx)
    else:
        result = await service.get(case.short_name, ctx)
        assert result.short_name == case.expect_short_name


# ---------------------------------------------------------------------------
# list()
# ---------------------------------------------------------------------------


@dataclass
class ListCase:
    desc: str
    entries: list = field(default_factory=list)  # (short_name, feature_flag) tuples
    enabled_features: list = field(default_factory=list)
    expect_visible: set[str] = field(default_factory=set)


LIST_CASES = [
    ListCase(
        desc="returns all unflagged sources",
        entries=[("slack", None), ("github", None)],
        expect_visible={"slack", "github"},
    ),
    ListCase(
        desc="filters flagged source without flag",
        entries=[("slack", None), ("gated", "sharepoint_2019_v2")],
        expect_visible={"slack"},
    ),
    ListCase(
        desc="includes flagged source when enabled",
        entries=[("slack", None), ("gated", "sharepoint_2019_v2")],
        enabled_features=[FeatureFlag.SHAREPOINT_2019_V2],
        expect_visible={"slack", "gated"},
    ),
    ListCase(
        desc="empty registry returns empty",
        entries=[],
        expect_visible=set(),
    ),
]


@pytest.mark.parametrize("case", LIST_CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_list(case: ListCase):
    registry = FakeSourceRegistry()
    for short_name, flag in case.entries:
        registry.seed(_make_entry(short_name, short_name.title(), feature_flag=flag))
    service = SourceService(source_registry=registry, settings=_make_settings())
    ctx = _make_ctx(enabled_features=case.enabled_features)

    result = await service.list(ctx)

    assert {s.short_name for s in result} == case.expect_visible


# ---------------------------------------------------------------------------
# Self-hosted BYOC override
# ---------------------------------------------------------------------------


@dataclass
class ByocCase:
    desc: str
    environment: str
    auth_methods: list[str]
    expect_byoc: bool


BYOC_CASES = [
    ByocCase(
        desc="oauth forced byoc on self-hosted",
        environment="self-hosted",
        auth_methods=["oauth_browser", "oauth_token"],
        expect_byoc=True,
    ),
    ByocCase(
        desc="oauth not forced byoc on cloud",
        environment="cloud",
        auth_methods=["oauth_browser", "oauth_token"],
        expect_byoc=False,
    ),
    ByocCase(
        desc="direct auth not forced byoc on self-hosted",
        environment="self-hosted",
        auth_methods=["direct"],
        expect_byoc=False,
    ),
]


@pytest.mark.parametrize("case", BYOC_CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_byoc(case: ByocCase):
    registry = FakeSourceRegistry()
    registry.seed(_make_entry("src", "Src", auth_methods=case.auth_methods))
    service = SourceService(source_registry=registry, settings=_make_settings(case.environment))
    ctx = _make_ctx()

    result = await service.get("src", ctx)

    assert result.requires_byoc is case.expect_byoc


# ---------------------------------------------------------------------------
# Schema mapping — single case, not table-driven
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_schema_fields_match_entry():
    registry = FakeSourceRegistry()
    registry.seed(_make_entry("slack", "Slack"))
    service = SourceService(source_registry=registry, settings=_make_settings())

    result = await service.get("slack", _make_ctx())

    assert result.name == "Slack"
    assert result.short_name == "slack"
    assert result.description == "Test Slack source"
    assert result.class_name == "SlackSource"
    assert result.auth_methods == ["direct"]
    assert result.supports_continuous is False
    assert result.federated_search is False
    assert result.output_entity_definitions == []
