"""Unit tests for EntityDefinitionRegistry.

Table-driven tests with patched ENTITIES_BY_SOURCE.
No real platform entities loaded.
"""

from dataclasses import dataclass, field
from unittest.mock import patch

import pytest

from airweave.domains.entities.registry import EntityDefinitionRegistry, _to_snake_case

_PATCH_ENTITIES = "airweave.domains.entities.registry.ENTITIES_BY_SOURCE"


# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------


def _make_entity_cls(class_name: str, doc: str | None = None) -> type:
    """Build a minimal stub entity class."""
    return type(class_name, (), {"__doc__": doc or f"Stub {class_name}"})


def _build_registry(entities_by_source: dict):
    """Build an EntityDefinitionRegistry with patched globals."""
    registry = EntityDefinitionRegistry()
    with patch(_PATCH_ENTITIES, entities_by_source):
        registry.build()
    return registry


# ---------------------------------------------------------------------------
# _to_snake_case
# ---------------------------------------------------------------------------


@dataclass
class SnakeCaseCase:
    desc: str
    input: str
    expected: str


SNAKE_CASES = [
    SnakeCaseCase("pascal case", "AsanaTaskEntity", "asana_task_entity"),
    SnakeCaseCase("single word", "Entity", "entity"),
    SnakeCaseCase("consecutive uppercase", "HTTPEntity", "http_entity"),
    SnakeCaseCase("already snake", "already_snake", "already_snake"),
    SnakeCaseCase("mixed with numbers", "S3BucketEntity", "s3_bucket_entity"),
]


@pytest.mark.parametrize("case", SNAKE_CASES, ids=lambda c: c.desc)
def test_to_snake_case(case: SnakeCaseCase):
    assert _to_snake_case(case.input) == case.expected


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------


@dataclass
class GetCase:
    desc: str
    short_name: str
    entities: dict = field(default_factory=lambda: {"asana": ["AsanaTaskEntity"]})
    expect_name: str | None = None  # None → expect KeyError


GET_CASES = [
    GetCase(
        desc="returns known entity",
        short_name="asana_task_entity",
        expect_name="AsanaTaskEntity",
    ),
    GetCase(
        desc="unknown raises KeyError",
        short_name="nonexistent",
        entities={},
    ),
]


@pytest.mark.parametrize("case", GET_CASES, ids=lambda c: c.desc)
def test_get(case: GetCase):
    entities = {src: [_make_entity_cls(n) for n in names] for src, names in case.entities.items()}
    registry = _build_registry(entities)

    if case.expect_name is None:
        with pytest.raises(KeyError):
            registry.get(case.short_name)
    else:
        assert registry.get(case.short_name).name == case.expect_name


# ---------------------------------------------------------------------------
# list_all()
# ---------------------------------------------------------------------------


@dataclass
class ListAllCase:
    desc: str
    entities: dict = field(default_factory=dict)
    expect_count: int = 0


LIST_ALL_CASES = [
    ListAllCase(
        desc="returns all entries",
        entities={"asana": ["AsanaTaskEntity"], "slack": ["SlackMessageEntity"]},
        expect_count=2,
    ),
    ListAllCase(desc="empty when no entities", entities={}, expect_count=0),
]


@pytest.mark.parametrize("case", LIST_ALL_CASES, ids=lambda c: c.desc)
def test_list_all(case: ListAllCase):
    entities = {src: [_make_entity_cls(n) for n in names] for src, names in case.entities.items()}
    registry = _build_registry(entities)
    assert len(registry.list_all()) == case.expect_count


# ---------------------------------------------------------------------------
# list_for_source()
# ---------------------------------------------------------------------------


@dataclass
class ListForSourceCase:
    desc: str
    entities: dict
    query_source: str
    expect_short_names: set[str]


LIST_FOR_SOURCE_CASES = [
    ListForSourceCase(
        desc="returns matching entries",
        entities={"asana": ["AsanaTaskEntity", "AsanaProjectEntity"], "slack": ["SlackMessageEntity"]},
        query_source="asana",
        expect_short_names={"asana_task_entity", "asana_project_entity"},
    ),
    ListForSourceCase(
        desc="empty for unknown source",
        entities={"asana": ["AsanaTaskEntity"]},
        query_source="nonexistent",
        expect_short_names=set(),
    ),
]


@pytest.mark.parametrize("case", LIST_FOR_SOURCE_CASES, ids=lambda c: c.desc)
def test_list_for_source(case: ListForSourceCase):
    entities = {src: [_make_entity_cls(n) for n in names] for src, names in case.entities.items()}
    registry = _build_registry(entities)
    result = registry.list_for_source(case.query_source)
    assert {e.short_name for e in result} == case.expect_short_names


# ---------------------------------------------------------------------------
# build() — entry fields
# ---------------------------------------------------------------------------


def test_module_name_stored():
    registry = _build_registry({"asana": [_make_entity_cls("AsanaTaskEntity")]})
    assert registry.get("asana_task_entity").module_name == "asana"


def test_description_from_docstring():
    cls = _make_entity_cls("AsanaTaskEntity", doc="Custom doc")
    registry = _build_registry({"asana": [cls]})
    assert registry.get("asana_task_entity").description == "Custom doc"


def test_entity_class_ref_stored():
    cls = _make_entity_cls("AsanaTaskEntity")
    registry = _build_registry({"asana": [cls]})
    assert registry.get("asana_task_entity").entity_class_ref is cls
