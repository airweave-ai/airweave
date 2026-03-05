"""Entity definition domain test fixtures."""

import pytest

from airweave.domains.entities.types import EntityDefinitionEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entity_entry(
    short_name: str = "asana_task_entity",
    name: str = "AsanaTaskEntity",
    *,
    module_name: str = "asana",
    description: str | None = None,
) -> EntityDefinitionEntry:
    """Build a minimal EntityDefinitionEntry for tests."""
    return EntityDefinitionEntry(
        short_name=short_name,
        name=name,
        description=description or f"Test {name}",
        class_name=name,
        entity_class_ref=type(name, (), {}),
        module_name=module_name,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def asana_task_entry():
    return _make_entity_entry("asana_task_entity", "AsanaTaskEntity", module_name="asana")


@pytest.fixture
def asana_project_entry():
    return _make_entity_entry("asana_project_entity", "AsanaProjectEntity", module_name="asana")


@pytest.fixture
def slack_message_entry():
    return _make_entity_entry("slack_message_entity", "SlackMessageEntity", module_name="slack")
