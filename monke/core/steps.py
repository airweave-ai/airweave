"""Test step implementations with parallelized verification and robust sync handling."""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from monke.core.config import TestConfig
from monke.core.context import TestContext
from monke.core import http_utils
from monke.utils.logging import get_logger


class TestStep(ABC):
    """Abstract base class for test steps."""

    def __init__(self, config: TestConfig, context: TestContext) -> None:
        """Initialize the test step."""
        self.config = config
        self.context = context
        self.logger = get_logger(f"test_step.{self.__class__.__name__}")

    def _display_name(self, entity: Dict[str, Any]) -> str:
        """Return a human-readable identifier for an entity regardless of type."""
        return (
            entity.get("path")
            or entity.get("title")
            or entity.get("id")
            or entity.get("url")
            or "<unknown>"
        )

    @abstractmethod
    async def execute(self) -> None:
        """Execute the test step."""
        raise NotImplementedError


class CreateStep(TestStep):
    """Create test entities step."""

    async def execute(self) -> None:
        """Create test entities via the connector."""
        self.logger.info("🥁 Creating test entities")

        bongo = self.context.bongo
        entities = await bongo.create_entities()

        # Optional post-create delay to allow upstream APIs to propagate data
        delay_seconds = 0
        try:
            delay_override = (
                self.config.connector.config_fields.get("post_create_sleep_seconds")
                if self.config.connector and self.config.connector.config_fields
                else None
            )
            if delay_override is not None:
                delay_seconds = int(delay_override)
        except Exception:
            delay_seconds = 0

        if delay_seconds > 0:
            self.logger.info(
                f"⏸️ Waiting {delay_seconds}s after creation to allow source API propagation"
            )
            await asyncio.sleep(delay_seconds)

        self.logger.info(f"✅ Created {len(entities)} test entities")

        # Store entities for later steps and on bongo for deletes
        self.context.created_entities = entities
        if self.context.bongo:
            self.context.bongo.created_entities = entities


class SyncStep(TestStep):
    """Sync data to Airweave step."""

    async def execute(self) -> None:
        """Trigger sync and wait for completion."""
        self.logger.info("🔄 Syncing data to Airweave")
        
        # Add delay to allow external APIs (like GitHub) to update their commit history
        # This prevents race conditions where sync runs before deletions are reflected in API
        self.logger.info("⏳ Waiting 30s for external API to reflect recent changes...")
        await asyncio.sleep(30)

        # If a job is already running, wait for it, BUT ALWAYS launch our own sync afterwards
        active_job_id = self._find_active_job_id()
        if active_job_id:
            self.logger.info(
                f"🟡 A sync is already in progress (job {active_job_id}); waiting for it to complete."
            )
            await self._wait_for_sync_completion(target_job_id=active_job_id)
            self.logger.info(
                "🧭 Previous sync finished; launching a fresh sync to capture recent changes"
            )

        # Try to start a new sync. If the server says one is already running, wait for that one,
        # then START OUR OWN sync and wait for it too.
        target_job_id: Optional[str] = None
        try:
            run_resp = http_utils.http_post(
                f"/source-connections/{self.context.source_connection_id}/run"
            )
            target_job_id = str(run_resp["id"])
        except Exception as e:
            msg = str(e).lower()
            if "already has a running job" in msg or "already running" in msg:
                self.logger.warning(
                    "⚠️ Sync already running; discovering and waiting for that job."
                )
                active_job_id = self._find_active_job_id() or self._get_latest_job_id()
                if not active_job_id:
                    # Last resort: brief wait then re-check
                    await asyncio.sleep(2.0)
                    active_job_id = (
                        self._find_active_job_id() or self._get_latest_job_id()
                    )
                if not active_job_id:
                    raise  # nothing to wait on; re-raise original error
                await self._wait_for_sync_completion(target_job_id=active_job_id)

                # IMPORTANT: after the previous job completes, start *our* job
                run_resp = http_utils.http_post(
                    f"/source-connections/{self.context.source_connection_id}/run"
                )
                target_job_id = str(run_resp["id"])
            else:
                raise  # unknown error

        await self._wait_for_sync_completion(target_job_id=target_job_id)
        self.logger.info("✅ Sync completed")

    def _get_jobs(self) -> List[Dict[str, Any]]:
        """Get list of sync jobs for the source connection, sorted by recency."""
        jobs = (
            http_utils.http_get(
                f"/source-connections/{self.context.source_connection_id}/jobs"
            )
            or []
        )
        # Sort by started_at or created_at, newest first
        return sorted(
            jobs,
            key=lambda j: j.get("started_at") or j.get("created_at") or "",
            reverse=True,
        )

    def _find_active_job_id(self) -> Optional[str]:
        """Find an active job from the jobs list."""
        ACTIVE = {"created", "pending", "in_progress", "running", "queued"}
        jobs = self._get_jobs()
        for job in jobs:
            if job.get("status", "").lower() in ACTIVE:
                return str(job["id"])
        return None

    def _get_latest_job_id(self) -> Optional[str]:
        """Get the latest job ID."""
        jobs = self._get_jobs()
        if jobs:
            return str(jobs[0]["id"])
        return None

    async def _wait_for_sync_completion(
        self,
        target_job_id: Optional[str] = None,
        timeout_seconds: int = 300,
    ) -> None:
        """Wait for sync job to complete."""
        self.logger.info("⏳ Waiting for sync to complete...")

        ACTIVE_STATUSES = {"created", "pending", "in_progress", "running", "queued"}

        # Find job ID if not provided
        if not target_job_id:
            target_job_id = self._find_active_job_id()

        # Still no job? Wait for one to appear
        if not target_job_id:
            self.logger.info("ℹ️ No job id available; waiting for new job...")
            start = time.monotonic()
            prev_latest = self.context.last_sync_job_id

            while time.monotonic() - start < timeout_seconds:
                # Try to get latest job
                latest_id = self._get_latest_job_id()
                if latest_id and latest_id != prev_latest:
                    target_job_id = latest_id
                    self.logger.info(f"🆔 Detected sync job id: {target_job_id}")
                    break
                await asyncio.sleep(2.0)

            if not target_job_id:
                raise RuntimeError("Couldn't obtain a sync job id to wait on.")

        # Poll for job completion
        start = time.monotonic()
        while time.monotonic() - start < timeout_seconds:
            # Find the job in our jobs list
            job = None
            try:
                jobs = self._get_jobs()
                for j in jobs:
                    if str(j["id"]) == str(target_job_id):
                        job = j
                        break
            except Exception as e:
                self.logger.warning(f"⚠️ Error fetching job status: {e}")

            if not job:
                await asyncio.sleep(2.0)
                continue

            # Check job status
            status = job.get("status", "").lower()
            completed_at = job.get("completed_at")
            error = job.get("error")

            self.logger.info(
                f"🔍 Job {target_job_id} status={status}, completed_at={completed_at}"
            )

            # Check for failure
            if status == "failed":
                raise RuntimeError(f"Sync failed: {error or 'unknown error'}")

            # Check for completion
            if status == "completed" and completed_at:
                self.context.last_sync_job_id = str(target_job_id)
                self.logger.info("✅ Sync completed successfully")
                return

            # Still running
            if status in ACTIVE_STATUSES:
                await asyncio.sleep(2.0)
                continue

            # Unexpected state
            await asyncio.sleep(0.5)

        raise TimeoutError("Sync timeout reached")


# ---------- Shared search helpers ----------


def _safe_results_from_search_response(resp) -> List[Dict[str, Any]]:
    """
    Accept either a Pydantic model or plain dict. Return list of result dicts.
    """
    if resp is None:
        return []

    try:
        data = resp.model_dump()
    except AttributeError:
        try:
            data = dict(resp)
        except Exception:
            data = {}

    results = data.get("results")
    if results is None and "items" in data:
        results = data["items"]

    if isinstance(results, list):
        return results
    return []


async def _search_collection_async(
    client, readable_id: str, query: str, limit: int = 1000
) -> List[Dict[str, Any]]:
    """
    Use Airweave's advanced search API endpoint with all extra features disabled.
    Always uses a limit of 1000 for comprehensive results.
    """

    # Build the search request with all extra features disabled
    search_request = {
        "query": query,
        "limit": 1000,  # Always use 1000 for comprehensive results
        "rerank": False,
        "interpret_filters": False,
        "expand_query": False,
        "generate_answer": False,
        "retrieval_strategy": "keyword",  # Use keyword search for exact string matching
    }

    try:
        data = http_utils.http_post(
            f"/collections/{readable_id}/search", json=search_request
        )
        return data.get("results", [])
    except Exception:
        return []


async def _token_present_in_collection(
    client, readable_id: str, token: str, limit: int = 1000
) -> bool:
    """
    Check if `token` appears in any result payload (case-insensitive).
    Uses a fixed limit of 1000 for comprehensive search.
    """
    try:
        # Always use 1000 limit for comprehensive results
        results = await _search_collection_async(client, readable_id, token, 1000)
        token_lower = token.lower()

        # Debug logging to help diagnose search issues
        logger = get_logger("monke")
        logger.info(f"🔍 Searching for token '{token}' in collection '{readable_id}'")
        logger.info(f"🔍 Found {len(results)} results from search")

        # Log all results for debugging
        for i, r in enumerate(results):
            payload = r.get("payload", {})
            score = r.get("score", 0)
            logger.info(
                f"   Result {i}: {payload.get('name', 'Unknown')} (score: {score})"
            )
            if i < 2:  # Show first 2 results in detail
                logger.info(f"      Payload: {str(payload)[:200]}...")

        for i, r in enumerate(results):
            payload = r.get("payload", {})
            if payload and token_lower in str(payload).lower():
                logger.info(
                    f"✅ Token '{token}' found in result {i}: {payload.get('name', 'Unknown')}"
                )
                return True

        logger.info(f"❌ Token '{token}' not found in any of {len(results)} results")
        return False
    except Exception as e:
        get_logger("monke").error(f"Error checking token present in collection: {e}")
        return False


def _search_limit_from_config(config: TestConfig, default: int = 50) -> int:
    """Get search limit from config or use default."""
    try:
        return int(config.verification_config.get("search_limit", default))
    except Exception:
        return default


# ---------- Verification steps (parallelized) ----------


class VerifyStep(TestStep):
    """Verify data in Qdrant step."""

    async def execute(self) -> None:
        self.logger.info("🔍 Verifying entities in Qdrant")
        client = self.context.airweave_client

        # Debug: Log collection info
        self.logger.info(
            f"🔍 Searching in collection: {self.context.collection_readable_id}"
        )
        self.logger.info(f"🔍 Verifying {len(self.context.created_entities)} entities")

        async def verify_one(entity: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
            expected_token = entity.get("token")
            if not expected_token:
                self.logger.warning(
                    "⚠️ No token found in entity, falling back to filename"
                )
                expected_token = (entity.get("path") or "").split("/")[-1]

            self.logger.info(
                f"🔍 Verifying entity: {self._display_name(entity)} with token: {expected_token}"
            )

            # Always use 1000 limit for comprehensive search
            ok = await _token_present_in_collection(
                client, self.context.collection_readable_id, expected_token, 1000
            )
            return entity, ok

        # Add a wait after sync completion to allow Qdrant indexing
        self.logger.info("⏳ Waiting 10s for Qdrant indexing to complete...")
        await asyncio.sleep(10)

        # Retry support + optional one-time rescue resync
        attempts = int(self.config.verification_config.get("retries", 5))
        backoff = float(
            self.config.verification_config.get("retry_backoff_seconds", 1.0)
        )
        resync_on_miss = bool(
            self.config.verification_config.get("resync_on_miss", True)
        )

        resync_lock = asyncio.Lock()
        resync_triggered = False

        async def verify_with_retries(e: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
            nonlocal resync_triggered

            for i in range(max(1, attempts)):
                entity, ok = await verify_one(e)
                if ok:
                    return entity, True
                await asyncio.sleep(backoff)

            if resync_on_miss:
                async with resync_lock:
                    if not resync_triggered:
                        resync_triggered = True
                        self.logger.info(
                            "🔁 Miss detected during verify; triggering an extra sync …"
                        )
                        # Reuse the same SyncStep logic to avoid duplication
                        await SyncStep(self.config, self.context).execute()
                # Final check after resync
                return await verify_one(e)

            return e, False

        results = await asyncio.gather(
            *[verify_with_retries(e) for e in self.context.created_entities]
        )

        errors = []
        for entity, ok in results:
            if not ok:
                errors.append(
                    f"Entity {self._display_name(entity)} not found in Qdrant"
                )
            else:
                self.logger.info(
                    f"✅ Entity {self._display_name(entity)} verified in Qdrant"
                )

        if errors:
            raise Exception("; ".join(errors))

        self.logger.info("✅ All entities verified in Qdrant")


class UpdateStep(TestStep):
    """Update test entities step."""

    async def execute(self) -> None:
        self.logger.info("📝 Updating test entities")
        bongo = self.context.bongo
        updated_entities = await bongo.update_entities()
        self.logger.info(f"✅ Updated {len(updated_entities)} test entities")
        self.context.updated_entities = updated_entities


class PartialDeleteStep(TestStep):
    """Partial deletion step - delete subset of entities based on test size."""

    async def execute(self) -> None:
        self.logger.info("🗑️ Executing partial deletion")
        bongo = self.context.bongo

        deletion_count = self._calculate_partial_deletion_count()
        entities_to_delete = self.context.created_entities[:deletion_count]
        entities_to_keep = self.context.created_entities[deletion_count:]

        self.logger.info(
            f"🗑️ Deleting {len(entities_to_delete)} entities: "
            f"{[self._display_name(e) for e in entities_to_delete]}"
        )
        self.logger.info(
            f"💾 Initially keeping {len(entities_to_keep)} entities: "
            f"{[self._display_name(e) for e in entities_to_keep]}"
        )

        deleted_paths = await bongo.delete_specific_entities(entities_to_delete)

        # IMPORTANT: The bongo may have deleted more entities than requested
        # (e.g., cascade deletions in ClickUp where deleting a task also deletes its children)
        # We need to update our tracking based on what was actually deleted

        # Build a set of deleted identifiers for fast lookup
        deleted_identifiers = set(deleted_paths)

        # Find all entities that were actually deleted (including cascade deletions)
        # Different bongos use different identifier fields (id vs path)
        actually_deleted = []
        actually_remaining = []

        for e in self.context.created_entities:
            # Check both 'id' and 'path' fields to support different bongo types
            entity_identifier = e.get("id") or e.get("path")
            if entity_identifier and entity_identifier in deleted_identifiers:
                actually_deleted.append(e)
            else:
                actually_remaining.append(e)

        # Update context with actual results
        self.context.partially_deleted_entities = actually_deleted
        self.context.remaining_entities = actually_remaining

        if len(actually_deleted) > len(entities_to_delete):
            cascade_count = len(actually_deleted) - len(entities_to_delete)
            self.logger.info(
                f"📎 Note: {cascade_count} additional entities were cascade-deleted "
                f"(total {len(actually_deleted)} deleted, {len(actually_remaining)} remaining)"
            )

        self.logger.info(
            f"✅ Partial deletion completed: {len(deleted_paths)} entities deleted"
        )

    def _calculate_partial_deletion_count(self) -> int:
        return self.config.deletion.partial_delete_count


class VerifyPartialDeletionStep(TestStep):
    """Verify that partially deleted entities are removed from Qdrant."""

    async def execute(self) -> None:
        self.logger.info("🔍 Verifying partial deletion")

        if not self.config.deletion.verify_partial_deletion:
            self.logger.info(
                "⏭️ Skipping partial deletion verification (disabled in config)"
            )
            return

        client = self.context.airweave_client

        self.logger.info("🔍 Expecting these entities to be deleted:")
        for entity in self.context.partially_deleted_entities:
            self.logger.info(
                f"   - {self._display_name(entity)} (token: {entity.get('token', 'N/A')})"
            )

        async def check_deleted(entity: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
            # Always use token for verification
            token = entity.get("token")
            if not token:
                self.logger.warning(
                    f"No token found for entity {self._display_name(entity)}"
                )
                return entity, True  # Assume deleted if no token

            # Check if token is present in collection
            present = await _token_present_in_collection(
                client, self.context.collection_readable_id, token, 1000
            )

            return entity, (not present)

        results = await asyncio.gather(
            *[check_deleted(e) for e in self.context.partially_deleted_entities]
        )

        errors = []
        for entity, is_removed in results:
            if not is_removed:
                errors.append(
                    f"Entity {self._display_name(entity)} still exists in Qdrant after deletion"
                )
            else:
                self.logger.info(
                    f"✅ Entity {self._display_name(entity)} confirmed removed from Qdrant"
                )

        if errors:
            raise Exception("; ".join(errors))

        self.logger.info("✅ Partial deletion verification completed")


class VerifyRemainingEntitiesStep(TestStep):
    """Verify that remaining entities are still present in Qdrant."""

    async def execute(self) -> None:
        self.logger.info("🔍 Verifying remaining entities are still present")

        if not self.config.deletion.verify_remaining_entities:
            self.logger.info(
                "⏭️ Skipping remaining entities verification (disabled in config)"
            )
            return

        client = self.context.airweave_client

        async def check_present(entity: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
            expected_token = entity.get("token") or (
                (entity.get("path", "").split("/")[-1])
                if entity.get("path")
                else str(entity.get("id", ""))
            )
            if not expected_token:
                return entity, False
            # Always use 1000 limit for comprehensive search
            present = await _token_present_in_collection(
                client, self.context.collection_readable_id, expected_token, 1000
            )
            return entity, present

        results = await asyncio.gather(
            *[check_present(e) for e in self.context.remaining_entities]
        )

        errors = []
        for entity, is_present in results:
            if not is_present:
                errors.append(
                    f"Entity {self._display_name(entity)} was incorrectly removed from Qdrant"
                )
            else:
                self.logger.info(
                    f"✅ Entity {self._display_name(entity)} confirmed still present in Qdrant"
                )

        if errors:
            raise Exception("; ".join(errors))

        self.logger.info("✅ Remaining entities verification completed")


class CompleteDeleteStep(TestStep):
    """Complete deletion step - delete all remaining entities."""

    async def execute(self) -> None:
        self.logger.info("🗑️ Executing complete deletion")

        bongo = self.context.bongo

        remaining_entities = self.context.remaining_entities
        if not remaining_entities:
            self.logger.info("ℹ️ No remaining entities to delete")
            return

        self.logger.info(f"🗑️ Deleting remaining {len(remaining_entities)} entities")

        deleted_paths = await bongo.delete_specific_entities(remaining_entities)

        self.logger.info(
            f"✅ Complete deletion completed: {len(deleted_paths)} entities deleted"
        )


class VerifyCompleteDeletionStep(TestStep):
    """Verify that all test entities are completely removed from Qdrant."""

    async def execute(self) -> None:
        self.logger.info("🔍 Verifying complete deletion")

        if not self.config.deletion.verify_complete_deletion:
            self.logger.info(
                "⏭️ Skipping complete deletion verification (disabled in config)"
            )
            return

        client = self.context.airweave_client

        all_test_entities = (
            self.context.partially_deleted_entities + self.context.remaining_entities
        )

        async def check_deleted(entity: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
            # Get token to search for
            expected_token = entity.get("token") or (
                (entity.get("path", "").split("/")[-1])
                if entity.get("path")
                else str(entity.get("id", ""))
            )

            if not expected_token:
                return entity, False

            # Always use 1000 limit for comprehensive search
            present = await _token_present_in_collection(
                client, self.context.collection_readable_id, expected_token, 1000
            )

            if present:
                # Let's see what was found
                self.logger.warning(
                    f"⚠️ Entity {self._display_name(entity)} still found with token: {expected_token}"
                )
                # Do a more detailed search to see what's in Qdrant
                try:
                    results = await _search_collection_async(
                        client, self.context.collection_readable_id, expected_token, 5
                    )
                    for r in results[:2]:  # Show first 2 results
                        payload = r.get("payload", {})
                        self.logger.info(
                            f"   Found in Qdrant: id={payload.get('id')}, name={payload.get('name')}"
                        )
                except Exception as e:
                    self.logger.debug(f"Could not get detailed results: {e}")

            return entity, (not present)

        results = await asyncio.gather(*[check_deleted(e) for e in all_test_entities])

        errors = []
        for entity, is_removed in results:
            if not is_removed:
                errors.append(
                    f"Entity {self._display_name(entity)} still exists in Qdrant after complete deletion"
                )
            else:
                self.logger.info(
                    f"✅ Entity {self._display_name(entity)} confirmed removed from Qdrant"
                )

        if errors:
            raise Exception("; ".join(errors))

        # Always use 1000 limit for comprehensive search
        collection_empty = await self._verify_collection_empty_of_test_data(
            client, 1000
        )
        if not collection_empty:
            self.logger.warning(
                "⚠️ Qdrant collection still contains some data (may be metadata entities)"
            )
        else:
            self.logger.info("✅ Qdrant collection confirmed empty of test data")

        self.logger.info("✅ Complete deletion verification completed")

    async def _verify_collection_empty_of_test_data(
        self, client: Any, limit: int
    ) -> bool:
        try:
            test_patterns = ["monke-test", "Monke Test"]

            async def search_one(pattern: str) -> Tuple[str, List[Dict[str, Any]]]:
                try:
                    results = await _search_collection_async(
                        client,
                        self.context.collection_readable_id,
                        pattern,
                        limit=min(limit, 25),
                    )
                    return pattern, results
                except Exception:
                    return pattern, []

            pattern_results = await asyncio.gather(
                *[search_one(p) for p in test_patterns]
            )

            total = 0
            for pattern, results in pattern_results:
                count = len(results)
                total += count
                if count:
                    self.logger.info(
                        f"🔍 Found {count} results for pattern '{pattern}'"
                    )
                    for r in results[:3]:
                        payload = r.get("payload", {})
                        score = r.get("score")
                        self.logger.info(
                            f"   - {payload.get('name', 'Unknown')} (score: {score})"
                        )

            if total == 0:
                self.logger.info("✅ No test data found in collection")
                return True
            else:
                self.logger.warning(f"⚠️ Found {total} test data results in collection")
                return False

        except Exception as e:
            self.logger.error(f"❌ Error verifying collection emptiness: {e}")
            return False


class CleanupStep(TestStep):
    """Cleanup step - clean up entire source workspace."""

    async def execute(self) -> None:
        """Clean up all test data from the source workspace."""
        self.logger.info("🧹 Cleaning up source workspace")
        bongo = self.context.bongo

        try:
            await bongo.cleanup()
            self.logger.info("✅ Source workspace cleanup completed")
        except Exception as e:
            # Don't fail the test if cleanup fails, just log the warning
            self.logger.warning(f"⚠️ Cleanup encountered issues: {e}")


class CollectionCleanupStep(TestStep):
    """Collection cleanup step - clean up old test collections from Airweave."""

    async def execute(self) -> None:
        """Clean up old test collections from Airweave."""
        self.logger.info("🧹 Cleaning up old test collections")

        cleanup_stats = {"collections_deleted": 0, "errors": 0}

        try:
            # Find all test collections
            test_collections = await self._find_test_collections()

            if test_collections:
                self.logger.info(
                    f"🔍 Found {len(test_collections)} test collections to clean up"
                )

                for collection in test_collections:
                    try:
                        response = http_utils.http_delete(
                            f"/collections/{collection['readable_id']}"
                        )
                        if response.status_code in [200, 204]:
                            cleanup_stats["collections_deleted"] += 1
                            self.logger.info(
                                f"✅ Deleted collection: {collection['name']} ({collection['readable_id']})"
                            )
                        else:
                            cleanup_stats["errors"] += 1
                            self.logger.warning(
                                f"⚠️ Failed to delete collection {collection['readable_id']}: {response.status_code}"
                            )
                    except Exception as e:
                        cleanup_stats["errors"] += 1
                        self.logger.warning(
                            f"⚠️ Failed to delete collection {collection['readable_id']}: {e}"
                        )

            # Log cleanup summary
            self.logger.info(
                f"🧹 Collection cleanup completed: {cleanup_stats['collections_deleted']} collections deleted, "
                f"{cleanup_stats['errors']} errors"
            )

        except Exception as e:
            self.logger.error(f"❌ Error during collection cleanup: {e}")
            # Don't re-raise - cleanup should be best-effort

    async def _find_test_collections(self) -> List[Dict[str, Any]]:
        """Find all test collections that should be cleaned up."""
        test_collections = []

        try:
            collections = http_utils.http_get("/collections")

            # Handle both list and dict with items/results key
            if isinstance(collections, dict):
                collections = collections.get("items", collections.get("results", []))

            for collection in collections:
                name = collection.get("name", "")
                readable_id = collection.get("readable_id", "")

                # Check if this looks like a test collection
                is_test_collection = (
                    name.lower().startswith("monke-")
                    or "test" in name.lower()
                    and ("collection" in name.lower() or "monke" in name.lower())
                    or readable_id.startswith("monke-")
                )

                if is_test_collection:
                    test_collections.append(collection)

        except Exception as e:
            self.logger.error(f"❌ Error finding test collections: {e}")

        return test_collections


class TestStepFactory:
    """Factory for creating test steps."""

    _steps = {
        "cleanup": CleanupStep,
        "collection_cleanup": CollectionCleanupStep,
        "create": CreateStep,
        "sync": SyncStep,
        "verify": VerifyStep,
        "update": UpdateStep,
        "partial_delete": PartialDeleteStep,
        "verify_partial_deletion": VerifyPartialDeletionStep,
        "verify_remaining_entities": VerifyRemainingEntitiesStep,
        "complete_delete": CompleteDeleteStep,
        "verify_complete_deletion": VerifyCompleteDeletionStep,
    }

    def create_step(
        self, step_name: str, config: TestConfig, context: TestContext
    ) -> TestStep:
        if step_name not in self._steps:
            raise ValueError(f"Unknown test step: {step_name}")
        return self._steps[step_name](config, context)
