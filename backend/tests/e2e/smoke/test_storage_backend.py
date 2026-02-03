"""
Smoke test for storage backend verification.

Tests that the configured storage backend is working correctly by:
1. Running a sync that writes data to storage (ARF files)
2. Verifying ARF files exist (in Docker container or local filesystem)
3. Verifying manifest and entity files are readable

Runs in local environment only (TEST_ENV=local) via @pytest.mark.local_only.
Skipped automatically in deployed environments (TEST_ENV=dev/prod).
"""

import asyncio
import json
import os
import subprocess
import uuid
from pathlib import Path

import httpx
import pytest


def is_container_running(container: str) -> bool:
    """Check if a Docker container is running."""
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", container],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def docker_exec(container: str, command: str) -> tuple[int, str, str]:
    """Run a command inside a Docker container.

    Returns (exit_code, stdout, stderr).
    """
    result = subprocess.run(
        ["docker", "exec", container, "sh", "-c", command],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def verify_arf_in_docker(sync_id: str, container: str = "airweave-temporal-worker") -> dict:
    """Verify ARF files exist inside the Docker container."""
    storage_path = "/app/local_storage"
    arf_path = f"{storage_path}/raw/{sync_id}"

    results = {
        "method": "docker",
        "container": container,
        "storage_exists": False,
        "arf_dir_exists": False,
        "manifest_exists": False,
        "manifest_valid": False,
        "entities_dir_exists": False,
        "entity_count": 0,
        "errors": [],
    }

    # Check storage directory
    code, out, err = docker_exec(container, f"test -d {storage_path} && echo 'yes' || echo 'no'")
    results["storage_exists"] = out.strip() == "yes"
    if not results["storage_exists"]:
        results["errors"].append(f"Storage directory {storage_path} not found in container")
        return results

    # Check ARF directory
    code, out, err = docker_exec(container, f"test -d {arf_path} && echo 'yes' || echo 'no'")
    results["arf_dir_exists"] = out.strip() == "yes"
    if not results["arf_dir_exists"]:
        code, out, err = docker_exec(container, f"ls -la {storage_path}/raw/ 2>/dev/null || echo 'raw dir missing'")
        results["errors"].append(f"ARF directory {arf_path} not found. Contents of raw/: {out.strip()}")
        return results

    # Check manifest
    manifest_path = f"{arf_path}/manifest.json"
    code, out, err = docker_exec(container, f"test -f {manifest_path} && echo 'yes' || echo 'no'")
    results["manifest_exists"] = out.strip() == "yes"
    if results["manifest_exists"]:
        code, out, err = docker_exec(container, f"python3 -c \"import json; json.load(open('{manifest_path}'))\" && echo 'valid'")
        results["manifest_valid"] = "valid" in out

    # Check entities directory
    entities_path = f"{arf_path}/entities"
    code, out, err = docker_exec(container, f"test -d {entities_path} && echo 'yes' || echo 'no'")
    results["entities_dir_exists"] = out.strip() == "yes"
    if results["entities_dir_exists"]:
        code, out, err = docker_exec(container, f"ls -1 {entities_path}/*.json 2>/dev/null | wc -l")
        try:
            results["entity_count"] = int(out.strip())
        except ValueError:
            results["entity_count"] = 0

    return results


def get_local_storage_paths() -> list[Path]:
    """Get possible local storage paths (for non-Docker runs)."""
    paths = []

    # Check STORAGE_PATH env var
    storage_path = os.environ.get("STORAGE_PATH")
    if storage_path:
        paths.append(Path(storage_path))

    # Common paths for local development
    paths.extend([
        Path("/tmp/airweave_local_storage"),
        Path("/tmp/airweave/local_storage"),
        Path("./local_storage").resolve(),
        Path(__file__).parent.parent.parent.parent.parent.parent / "local_storage",
    ])

    return paths


def verify_arf_locally(sync_id: str) -> dict:
    """Verify ARF files exist on local filesystem."""
    results = {
        "method": "local",
        "storage_exists": False,
        "arf_dir_exists": False,
        "manifest_exists": False,
        "manifest_valid": False,
        "entities_dir_exists": False,
        "entity_count": 0,
        "errors": [],
        "storage_path": None,
    }

    # Try each possible storage path
    for storage_path in get_local_storage_paths():
        if storage_path.exists():
            results["storage_exists"] = True
            results["storage_path"] = str(storage_path)

            arf_path = storage_path / "raw" / sync_id
            if arf_path.exists():
                results["arf_dir_exists"] = True

                # Check manifest
                manifest_path = arf_path / "manifest.json"
                if manifest_path.exists():
                    results["manifest_exists"] = True
                    try:
                        with open(manifest_path) as f:
                            json.load(f)
                        results["manifest_valid"] = True
                    except json.JSONDecodeError:
                        results["errors"].append(f"Invalid JSON in manifest at {manifest_path}")

                # Check entities
                entities_path = arf_path / "entities"
                if entities_path.exists():
                    results["entities_dir_exists"] = True
                    entity_files = list(entities_path.glob("*.json"))
                    results["entity_count"] = len(entity_files)

                return results  # Found ARF files, return

    if not results["storage_exists"]:
        results["errors"].append(f"No storage directory found. Checked: {[str(p) for p in get_local_storage_paths()]}")
    elif not results["arf_dir_exists"]:
        results["errors"].append(f"ARF directory not found for sync_id={sync_id} in {results['storage_path']}")

    return results


def verify_arf_files(sync_id: str) -> dict:
    """Verify ARF files exist - tries Docker first, then local filesystem."""
    # Try Docker containers first
    for container in ["airweave-temporal-worker", "airweave-backend"]:
        if is_container_running(container):
            results = verify_arf_in_docker(sync_id, container)
            if results["arf_dir_exists"]:
                return results
            # Container running but no ARF files - might be using different storage

    # Fall back to local filesystem
    return verify_arf_locally(sync_id)


@pytest.mark.asyncio
@pytest.mark.local_only
class TestStorageBackend:
    """Test suite for storage backend verification.

    @pytest.mark.local_only ensures this only runs when TEST_ENV=local.
    In deployed environments (TEST_ENV=dev), this is automatically skipped.
    """

    async def test_health_check_passes(self, api_client: httpx.AsyncClient):
        """Test that health check passes."""
        response = await api_client.get("/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        health = response.json()
        assert health.get("status") == "healthy", f"Unhealthy status: {health}"

    async def test_sync_writes_arf_files_to_storage(self, api_client: httpx.AsyncClient, config):
        """Test that sync writes ARF files to the storage backend.

        1. Creates a stub connection and triggers a sync
        2. Waits for sync to complete
        3. Verifies ARF files exist (in Docker or local filesystem)
        """
        collection_name = f"Storage Test {uuid.uuid4().hex[:8]}"

        # Create test collection
        collection_response = await api_client.post(
            "/collections/", json={"name": collection_name}
        )
        assert collection_response.status_code == 200, (
            f"Failed to create collection: {collection_response.text}"
        )
        collection = collection_response.json()
        collection_id = collection["readable_id"]

        try:
            # Check stub source is available
            sources_response = await api_client.get("/sources/")
            assert sources_response.status_code == 200, f"Sources API failed: {sources_response.text}"
            sources = sources_response.json()
            source_names = [s["short_name"] for s in sources]
            assert "stub" in source_names, (
                f"Stub source not available. ENABLE_INTERNAL_SOURCES must be true. "
                f"Available sources: {source_names}"
            )

            # Create stub connection and trigger sync
            connection_response = await api_client.post(
                "/source-connections",
                json={
                    "name": f"Storage Test {uuid.uuid4().hex[:8]}",
                    "short_name": "stub",
                    "readable_collection_id": collection_id,
                    "authentication": {"credentials": {"stub_key": "test"}},
                    "sync_immediately": True,
                },
            )
            assert connection_response.status_code == 200, (
                f"Failed to create stub connection: {connection_response.text}"
            )

            connection = connection_response.json()
            connection_id = connection["id"]
            sync_id = connection.get("sync_id")

            try:
                # Wait for sync to complete
                max_wait = 120
                poll_interval = 3
                elapsed = 0
                sync_completed = False

                while elapsed < max_wait:
                    await asyncio.sleep(poll_interval)
                    elapsed += poll_interval

                    status_response = await api_client.get(
                        f"/source-connections/{connection_id}"
                    )
                    if status_response.status_code != 200:
                        continue

                    conn_details = status_response.json()
                    status = conn_details.get("status")
                    sync_id = conn_details.get("sync_id") or sync_id

                    if status == "active":
                        sync_completed = True
                        break
                    elif status == "error":
                        pytest.fail(f"Sync failed with error: {conn_details}")

                assert sync_completed, f"Sync did not complete within {max_wait}s"
                assert sync_id, "No sync_id returned from connection"

                # Wait for filesystem writes to complete
                await asyncio.sleep(2)

                # VERIFY STORAGE - check Docker or local filesystem
                results = verify_arf_files(sync_id)

                # Assert all checks passed
                assert results["storage_exists"], (
                    f"Storage directory not found. Method: {results['method']}. "
                    f"Errors: {results['errors']}"
                )
                assert results["arf_dir_exists"], (
                    f"ARF directory not found for sync_id={sync_id}. "
                    f"Method: {results['method']}. Errors: {results['errors']}"
                )
                assert results["manifest_exists"], (
                    f"Manifest not found for sync_id={sync_id}"
                )
                assert results["manifest_valid"], (
                    f"Manifest is not valid JSON for sync_id={sync_id}"
                )
                assert results["entities_dir_exists"], (
                    f"Entities directory not found for sync_id={sync_id}"
                )
                assert results["entity_count"] > 0, (
                    f"No entity files found for sync_id={sync_id}"
                )

            finally:
                # Cleanup connection
                try:
                    await api_client.delete(f"/source-connections/{connection_id}")
                except Exception:
                    pass

        finally:
            # Cleanup collection
            try:
                await api_client.delete(f"/collections/{collection_id}")
            except Exception:
                pass
