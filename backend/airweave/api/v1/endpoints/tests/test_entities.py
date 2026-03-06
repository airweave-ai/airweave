"""API tests for entity definition endpoints.

Tests the entities API with a faked EntityDefinitionRegistry injected via DI.
Verifies HTTP routing, serialization, and empty-result handling.
"""

import pytest

from airweave.domains.entities.types import EntityDefinitionEntry


def _make_entry(
    short_name: str = "asana_task_entity",
    module_name: str = "asana",
) -> EntityDefinitionEntry:
    return EntityDefinitionEntry(
        short_name=short_name,
        name=short_name.title().replace("_", ""),
        description=f"Test {short_name}",
        class_name=short_name.title().replace("_", ""),
        entity_class_ref=type(short_name, (), {}),
        module_name=module_name,
        entity_type="json",
        entity_schema={"type": "object", "properties": {}},
    )


class TestEntityDefinitionsBySource:
    """Tests for GET /entities/definitions/by-source/."""

    @pytest.mark.asyncio
    async def test_returns_entries_for_known_source(self, client, fake_entity_definition_registry):
        fake_entity_definition_registry.seed(
            _make_entry("asana_task_entity", "asana"),
            _make_entry("asana_project_entity", "asana"),
        )

        response = await client.get(
            "/entities/definitions/by-source/",
            params={"source_short_name": "asana"},
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2
        assert {e["short_name"] for e in data} == {
            "asana_task_entity",
            "asana_project_entity",
        }

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_source(self, client):
        response = await client.get(
            "/entities/definitions/by-source/",
            params={"source_short_name": "nonexistent"},
        )
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_response_shape(self, client, fake_entity_definition_registry):
        fake_entity_definition_registry.seed(
            _make_entry("slack_message_entity", "slack"),
        )

        response = await client.get(
            "/entities/definitions/by-source/",
            params={"source_short_name": "slack"},
        )
        assert response.status_code == 200

        entry = response.json()[0]
        assert entry["short_name"] == "slack_message_entity"
        assert entry["module_name"] == "slack"
        assert entry["entity_type"] == "json"
        assert "entity_schema" in entry
        assert "entity_class_ref" not in entry

    @pytest.mark.asyncio
    async def test_does_not_leak_other_sources(self, client, fake_entity_definition_registry):
        fake_entity_definition_registry.seed(
            _make_entry("asana_task_entity", "asana"),
            _make_entry("slack_message_entity", "slack"),
        )

        response = await client.get(
            "/entities/definitions/by-source/",
            params={"source_short_name": "asana"},
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["short_name"] == "asana_task_entity"
