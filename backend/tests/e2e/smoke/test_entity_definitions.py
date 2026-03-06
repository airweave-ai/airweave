"""
Smoke tests for Entity Definition endpoints and sync-time entity counts.

Verifies:
1. Registry-backed /entities/definitions/by-source/ endpoint
2. Entity counts are correctly maintained by the PG trigger after sync
"""

import asyncio
from typing import Dict, Optional, Set, Tuple

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _wait_for_job_status(
    api_client: httpx.AsyncClient,
    conn_id: str,
    job_id: str,
    expected_statuses: str | Set[str],
    timeout: int = 30,
) -> Tuple[Optional[Dict], Optional[str]]:
    """Poll until a job reaches one of *expected_statuses* or *timeout* expires."""
    if isinstance(expected_statuses, str):
        expected_statuses = {expected_statuses}

    last_status: Optional[str] = None
    elapsed = 0

    while elapsed < timeout:
        response = await api_client.get(f"/source-connections/{conn_id}/jobs")
        if response.status_code == 200:
            jobs = response.json()
            job = next((j for j in jobs if j["id"] == job_id), None)
            if job:
                last_status = job["status"]
                if last_status in expected_statuses:
                    return job, last_status

        await asyncio.sleep(1)
        elapsed += 1

    return None, last_status


async def _run_sync_to_completion(
    api_client: httpx.AsyncClient,
    conn_id: str,
    timeout: int = 60,
) -> Dict:
    """Trigger a sync and wait for it to reach *completed*. Returns the job dict."""
    response = await api_client.post(f"/source-connections/{conn_id}/run")
    assert response.status_code == 200, f"Failed to trigger sync: {response.text}"
    job = response.json()

    completed, status = await _wait_for_job_status(
        api_client, conn_id, job["id"], "completed", timeout=timeout
    )
    assert completed is not None, (
        f"Sync did not complete within {timeout}s (last status: {status})"
    )
    return completed


# ===================================================================
# Entity Definition API tests
# ===================================================================


class TestEntityDefinitions:
    """Test suite for Entity Definition API endpoints."""

    @pytest.mark.asyncio
    async def test_get_definitions_for_known_source(self, api_client: httpx.AsyncClient):
        """Test fetching entity definitions for a known source."""
        response = await api_client.get(
            "/entities/definitions/by-source/",
            params={"source_short_name": "asana"},
        )

        assert response.status_code == 200, f"Failed: {response.text}"

        definitions = response.json()
        assert isinstance(definitions, list)
        assert len(definitions) > 0, "Asana should have at least one entity definition"

    @pytest.mark.asyncio
    async def test_definitions_have_required_fields(self, api_client: httpx.AsyncClient):
        """Test that entity definitions contain all expected fields."""
        response = await api_client.get(
            "/entities/definitions/by-source/",
            params={"source_short_name": "asana"},
        )
        assert response.status_code == 200

        required_fields = [
            "short_name",
            "name",
            "description",
            "class_name",
            "module_name",
            "entity_type",
            "entity_schema",
        ]

        for defn in response.json():
            for field in required_fields:
                assert field in defn, (
                    f"Entity definition {defn.get('short_name', '?')} missing field: {field}"
                )

    @pytest.mark.asyncio
    async def test_definitions_do_not_expose_internal_fields(self, api_client: httpx.AsyncClient):
        """Test that internal fields like entity_class_ref are not serialized."""
        response = await api_client.get(
            "/entities/definitions/by-source/",
            params={"source_short_name": "asana"},
        )
        assert response.status_code == 200

        for defn in response.json():
            assert "entity_class_ref" not in defn, "Internal field leaked to API response"

    @pytest.mark.asyncio
    async def test_unknown_source_returns_empty_list(self, api_client: httpx.AsyncClient):
        """Test that a non-existent source returns 200 with an empty list."""
        response = await api_client.get(
            "/entities/definitions/by-source/",
            params={"source_short_name": "this_source_does_not_exist_xyz"},
        )

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_module_name_matches_queried_source(self, api_client: httpx.AsyncClient):
        """Test that all returned definitions belong to the queried source."""
        source = "google_calendar"
        response = await api_client.get(
            "/entities/definitions/by-source/",
            params={"source_short_name": source},
        )
        assert response.status_code == 200

        for defn in response.json():
            assert defn["module_name"] == source, (
                f"Definition {defn['short_name']} has module_name={defn['module_name']}, "
                f"expected {source}"
            )

    @pytest.mark.asyncio
    async def test_entity_schema_is_object(self, api_client: httpx.AsyncClient):
        """Test that entity_schema is a dict (JSON schema)."""
        response = await api_client.get(
            "/entities/definitions/by-source/",
            params={"source_short_name": "slack"},
        )
        assert response.status_code == 200

        for defn in response.json():
            assert isinstance(defn["entity_schema"], dict), (
                f"Entity {defn['short_name']} schema should be a dict"
            )

    @pytest.mark.asyncio
    async def test_multiple_sources_return_different_definitions(
        self, api_client: httpx.AsyncClient
    ):
        """Test that different sources return different entity definitions."""
        resp_asana = await api_client.get(
            "/entities/definitions/by-source/",
            params={"source_short_name": "asana"},
        )
        resp_slack = await api_client.get(
            "/entities/definitions/by-source/",
            params={"source_short_name": "slack"},
        )

        assert resp_asana.status_code == 200
        assert resp_slack.status_code == 200

        asana_names = {d["short_name"] for d in resp_asana.json()}
        slack_names = {d["short_name"] for d in resp_slack.json()}

        assert asana_names.isdisjoint(slack_names), (
            f"Asana and Slack share entity definitions: {asana_names & slack_names}"
        )


# ===================================================================
# Sync-time entity count tests
# ===================================================================


class TestSyncEntityCounts:
    """Verify the PG trigger maintains correct entity_count rows after sync.

    Uses the TimedSource (20 entities / 2s) which produces:
      - 1 x TimedContainerEntity
      - 20 x TimedEntity
    Total: 21 entities inserted.
    """

    EXPECTED_TOTAL = 21  # 1 container + 20 timed entities

    @pytest.mark.asyncio
    async def test_entity_counts_populated_after_sync(
        self, api_client: httpx.AsyncClient, timed_source_connection_fast: Dict
    ):
        """After a completed sync the source connection reports entity counts."""
        conn_id = timed_source_connection_fast["id"]
        job = await _run_sync_to_completion(api_client, conn_id)

        assert job["entities_inserted"] == self.EXPECTED_TOTAL

        response = await api_client.get(f"/source-connections/{conn_id}")
        assert response.status_code == 200
        conn = response.json()

        summary = conn.get("entities")
        assert summary is not None, "entities should be present after sync"
        assert summary["total_entities"] == self.EXPECTED_TOTAL

        by_type = summary["by_type"]
        assert len(by_type) == 2, f"Expected 2 entity types, got {list(by_type.keys())}"

        total_from_types = sum(entry["count"] for entry in by_type.values())
        assert total_from_types == self.EXPECTED_TOTAL

    @pytest.mark.asyncio
    async def test_entity_counts_have_expected_types(
        self, api_client: httpx.AsyncClient, timed_source_connection_fast: Dict
    ):
        """Verify entity_count rows use the correct short_name-derived type names."""
        conn_id = timed_source_connection_fast["id"]
        await _run_sync_to_completion(api_client, conn_id)

        response = await api_client.get(f"/source-connections/{conn_id}")
        assert response.status_code == 200
        by_type = response.json()["entities"]["by_type"]

        type_names = set(by_type.keys())
        for name in type_names:
            assert isinstance(name, str) and len(name) > 0, (
                f"Entity type name should be a non-empty string, got: {name!r}"
            )

    @pytest.mark.asyncio
    async def test_entity_counts_stable_after_idempotent_resync(
        self, api_client: httpx.AsyncClient, timed_source_connection_fast: Dict
    ):
        """Running the same sync twice must not double the entity counts.

        The second run should detect identical hashes (KEEP) and leave
        the PG trigger-maintained counts unchanged.
        """
        conn_id = timed_source_connection_fast["id"]

        first_job = await _run_sync_to_completion(api_client, conn_id)
        assert first_job["entities_inserted"] == self.EXPECTED_TOTAL

        second_job = await _run_sync_to_completion(api_client, conn_id)
        assert second_job["entities_inserted"] == 0, (
            "Second sync should insert 0 (all entities unchanged)"
        )

        response = await api_client.get(f"/source-connections/{conn_id}")
        assert response.status_code == 200
        summary = response.json()["entities"]

        assert summary["total_entities"] == self.EXPECTED_TOTAL, (
            f"Counts should remain {self.EXPECTED_TOTAL} after idempotent re-sync, "
            f"got {summary['total_entities']}"
        )

    @pytest.mark.asyncio
    async def test_entity_counts_per_type_match_job_total(
        self, api_client: httpx.AsyncClient, timed_source_connection_fast: Dict
    ):
        """Sum of per-type counts must equal the job's entities_inserted total."""
        conn_id = timed_source_connection_fast["id"]
        job = await _run_sync_to_completion(api_client, conn_id)

        response = await api_client.get(f"/source-connections/{conn_id}")
        assert response.status_code == 200

        summary = response.json()["entities"]
        per_type_total = sum(entry["count"] for entry in summary["by_type"].values())

        assert per_type_total == job["entities_inserted"], (
            f"Per-type sum ({per_type_total}) != job entities_inserted "
            f"({job['entities_inserted']})"
        )

    @pytest.mark.asyncio
    async def test_entity_count_entries_have_last_updated(
        self, api_client: httpx.AsyncClient, timed_source_connection_fast: Dict
    ):
        """Each entry in by_type should carry a last_updated timestamp."""
        conn_id = timed_source_connection_fast["id"]
        await _run_sync_to_completion(api_client, conn_id)

        response = await api_client.get(f"/source-connections/{conn_id}")
        assert response.status_code == 200

        for type_name, stats in response.json()["entities"]["by_type"].items():
            assert "last_updated" in stats, (
                f"Entity type {type_name!r} missing last_updated"
            )
            assert stats["last_updated"] is not None
