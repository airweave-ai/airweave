"""API tests for sources endpoints.

Tests the sources API with a faked SourceService injected via DI.
Verifies HTTP routing, serialization, and SourceNotFoundError -> 404 via middleware.
"""

import pytest

from airweave.schemas.source import Source


def _make_source(short_name: str = "github", name: str = "GitHub") -> Source:
    """Build a minimal Source schema for testing."""
    return Source(
        name=name,
        short_name=short_name,
        description=f"Test {name} source",
        class_name=f"{name}Source",
        auth_methods=["direct"],
        auth_fields={"fields": []},
        config_fields={"fields": []},
        supported_auth_providers=[],
        output_entity_definitions=[],
    )


class TestSourcesList:
    """Tests for GET /sources."""

    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        response = await client.get("/sources")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_returns_seeded_sources(self, client, fake_source_service):
        fake_source_service.seed(_make_source("github"), _make_source("slack", "Slack"))

        response = await client.get("/sources")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 2
        assert {s["short_name"] for s in data} == {"github", "slack"}


class TestSourcesGet:
    """Tests for GET /sources/{short_name}."""

    @pytest.mark.asyncio
    async def test_get_existing_source(self, client, fake_source_service):
        fake_source_service.seed(_make_source("github"))

        response = await client.get("/sources/github")
        assert response.status_code == 200
        assert response.json()["short_name"] == "github"

    @pytest.mark.asyncio
    async def test_get_missing_source_returns_404(self, client):
        """SourceNotFoundError propagates through middleware to 404."""
        response = await client.get("/sources/nonexistent")
        assert response.status_code == 404
        assert "Source not found: nonexistent" in response.json()["detail"]
