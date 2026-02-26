"""Test step implementations with parallelized verification and robust sync handling."""

import asyncio
import os
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
        entity_count = self.config.entity_count

        self.logger.info("=" * 80)
        self.logger.info("🥁 CREATE PHASE: Generating test entities in source system")
        self.logger.info("=" * 80)
        self.logger.info(f"📡 Source: {self.config.connector.type}")
        self.logger.info(f"🎯 Target: Create {entity_count} test entities with tracking tokens")

        bongo = self.context.bongo
        entities = await bongo.create_entities()

        self.logger.info(f"✅ Successfully created {len(entities)} entities in {self.config.connector.type}")

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
            self.logger.info(f"⏸️ Post-create delay: Waiting {delay_seconds}s for API propagation...")
            self.logger.info("   (This allows the source system to index newly created entities)")
            await asyncio.sleep(delay_seconds)

        self.logger.info("=" * 80)
        self.logger.info(f"✅ CREATE COMPLETED: {len(entities)} test entities ready for sync")
        self.logger.info("=" * 80)

        # Store entities for later steps and on bongo for deletes
        self.context.created_entities = entities
        if self.context.bongo:
            self.context.bongo.created_entities = entities


class SyncStep(TestStep):
    """Sync data to Airweave step."""

    def __init__(self, config, context, force_full_sync: bool = False):
        """Initialize sync step.

        Args:
            config: Test configuration
            context: Test context
            force_full_sync: If True, forces a full sync ignoring cursor data
                           (only applicable for continuous syncs)
        """
        super().__init__(config, context)
        self.force_full_sync = force_full_sync

    async def execute(self) -> None:
        """Trigger sync and wait for completion."""
        self.logger.info("=" * 80)
        sync_mode = "FORCE FULL SYNC" if self.force_full_sync else "SYNC"
        self.logger.info(f"🔄 {sync_mode} PHASE: Triggering data synchronization pipeline")
        if self.force_full_sync:
            self.logger.info("   🌀 Force full sync enabled - will ignore cursor data and fetch all entities")
        self.logger.info("=" * 80)

        self.logger.info(f"📡 Source: {self.config.connector.type}")
        self.logger.info(f"🎯 Target: {self.context.collection_readable_id}")

        # Add delay to allow external APIs (like GitHub) to update their commit history
        # This prevents race conditions where sync runs before deletions are reflected in API
        self.logger.info("⏳ Pre-sync delay: Waiting 30s for external API to index changes...")
        self.logger.info("   (This ensures newly created/modified entities are available in the source API)")
        await asyncio.sleep(30)

        # If a job is already running, wait for it, BUT ALWAYS launch our own sync afterwards
        active_job_id = self._find_active_job_id()
        if active_job_id:
            self.logger.info(
                f"🟡 A sync is already in progress (job {active_job_id}); waiting for it to complete."
            )
            self.logger.info(
                "💡 Tip: You can monitor backend sync logs for detailed pipeline execution information"
            )
            await self._wait_for_sync_completion(target_job_id=active_job_id)
            self.logger.info(
                "🧭 Previous sync finished; launching a fresh sync to capture recent changes"
            )

        # Prepare query parameters for the sync request
        params = {}
        if self.force_full_sync:
            params["force_full_sync"] = "true"

        # Try to start a new sync. If the server says one is already running, wait for that one,
        # then START OUR OWN sync and wait for it too.
        target_job_id: Optional[str] = None
        try:
            run_resp = http_utils.http_post(
                f"/source-connections/{self.context.source_connection_id}/run",
                params=params,
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
                    f"/source-connections/{self.context.source_connection_id}/run",
                    params=params,
                )
                target_job_id = str(run_resp["id"])
            else:
                raise  # unknown error

        await self._wait_for_sync_completion(target_job_id=target_job_id)

        self.logger.info("=" * 80)
        self.logger.info(f"✅ {sync_mode} COMPLETED: Data pipeline execution finished successfully")
        self.logger.info(f"📊 Job ID: {target_job_id}")
        self.logger.info("📝 Note: Check backend logs for detailed sync pipeline metrics (entities processed, errors, etc.)")
        self.logger.info("=" * 80)

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
        timeout_seconds: int = 600,
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

            # Check for cancellation
            if status == "cancelled":
                raise RuntimeError(f"Sync was cancelled (job {target_job_id})")

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
    client, readable_id: str, token: str, limit: int = 1000, expect_present: bool = True
) -> bool:
    """
    Check if `token` appears in any search result (case-insensitive).
    Uses a fixed limit of 1000 for comprehensive search.

    Note: Search results use the new AirweaveSearchResult structure where fields
    like `name`, `id`, `textual_representation` are at the top level (not nested
    in a `payload` dict).

    Args:
        client: Airweave client
        readable_id: Collection ID
        token: Token to search for
        limit: Search limit (always 1000)
        expect_present: Whether we expect the token to be present (for logging context)
    """
    try:
        # Always use 1000 limit for comprehensive results
        results = await _search_collection_async(client, readable_id, token, 1000)
        token_lower = token.lower()

        # Context-aware logging
        logger = get_logger("monke")
        logger.info(f"🔍 Searching for token '{token}' in collection '{readable_id}'")
        logger.info(f"📊 Search returned {len(results)} result(s) from vector database")

        # Log sample results for debugging (only if results exist)
        if results and len(results) > 0:
            logger.info("📋 Sample results (showing up to 3):")
            for i, r in enumerate(results[:3]):
                score = r.get("score", 0)
                # New structure: name is at top level, not in payload
                name = r.get("name") or r.get("id", "Unknown")
                logger.info(f"   • Result {i+1}: {name} (score: {score:.3f})")

        # Check if token is present in any result
        # New structure: search entire result dict (fields are at top level)
        for i, r in enumerate(results):
            if r and token_lower in str(r).lower():
                if expect_present:
                    logger.info(f"✅ Token '{token}' found in vector database (as expected)")
                else:
                    logger.warning(f"⚠️ Token '{token}' found but was expected to be deleted!")
                return True

        # Token not found
        if expect_present:
            logger.warning(f"❌ Token '{token}' NOT found in vector database (expected to be present)")
        else:
            logger.info(f"✅ Token '{token}' confirmed absent from vector database (as expected)")
        return False

    except Exception as e:
        get_logger("monke").error(f"❌ Error checking token in collection: {e}")
        return False


def _search_limit_from_config(config: TestConfig, default: int = 50) -> int:
    """Get search limit from config or use default."""
    try:
        return int(config.verification_config.get("search_limit", default))
    except Exception:
        return default


# ---------- Verification steps (parallelized) ----------


class VerifyStep(TestStep):
    """Verify data in vector database step."""

    async def execute(self) -> None:
        self.logger.info("=" * 80)
        self.logger.info("📋 VERIFICATION PHASE: Checking entities in vector database")
        self.logger.info("=" * 80)

        client = self.context.airweave_client
        entity_count = len(self.context.created_entities)

        self.logger.info(f"🎯 Target: Verify {entity_count} entities were successfully synced")
        self.logger.info(f"📦 Collection: {self.context.collection_readable_id}")
        self.logger.info("🔍 Strategy: Search for unique tokens embedded in each test entity")

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

        # Add a wait after sync completion to allow vector database indexing
        self.logger.info("⏳ Waiting 10s for vector database indexing to complete...")
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

        # Generate detailed summary
        errors = []
        verified_count = 0
        for entity, ok in results:
            if not ok:
                errors.append(
                    f"Entity {self._display_name(entity)} not found in vector database"
                )
            else:
                verified_count += 1
                self.logger.info(
                    f"✅ [{verified_count}/{entity_count}] Entity {self._display_name(entity)} verified"
                )

        # Print narrative summary
        self.logger.info("=" * 80)
        if errors:
            self.logger.error(f"❌ VERIFICATION FAILED: {verified_count}/{entity_count} entities found")
            self.logger.error(f"📊 Summary: {len(errors)} entity(ies) missing from vector database")
            for error in errors:
                self.logger.error(f"   • {error}")
            self.logger.info("")
            self.logger.info("🔍 TROUBLESHOOTING TIPS:")
            self.logger.info("   1. Check if entities were created successfully in the source system")
            self.logger.info("   2. Review backend sync logs to see if source API returned the entities")
            self.logger.info("   3. Verify filter configurations aren't excluding test entities")
            self.logger.info("   4. Ensure adequate wait time for source API indexing (post_create_sleep_seconds)")
            self.logger.info("=" * 80)
            raise Exception("; ".join(errors))
        else:
            self.logger.info(f"✅ VERIFICATION PASSED: All {entity_count}/{entity_count} entities found!")
            self.logger.info("📊 Summary: Every test entity was successfully synced to the vector database")
            self.logger.info("=" * 80)


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
        # Convert to strings for consistent comparison (bongos may return int or str IDs)
        deleted_identifiers = set(str(p) for p in deleted_paths)

        # Find all entities that were actually deleted (including cascade deletions)
        # Different bongos use different identifier fields (id vs path)
        actually_deleted = []
        actually_remaining = []

        for e in self.context.created_entities:
            # Check both 'id' and 'path' fields to support different bongo types
            # Convert to string for consistent comparison with deleted_identifiers
            entity_identifier = str(e.get("id") or e.get("path") or "")
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
    """Verify that partially deleted entities are removed from vector database."""

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

            # Check if token is present in collection (expecting it to be absent/deleted)
            present = await _token_present_in_collection(
                client, self.context.collection_readable_id, token, 1000, expect_present=False
            )

            return entity, (not present)

        results = await asyncio.gather(
            *[check_deleted(e) for e in self.context.partially_deleted_entities]
        )

        errors = []
        for entity, is_removed in results:
            if not is_removed:
                errors.append(
                    f"Entity {self._display_name(entity)} still exists in vector database after deletion"
                )
            else:
                self.logger.info(
                    f"✅ Entity {self._display_name(entity)} confirmed removed from vector database"
                )

        if errors:
            raise Exception("; ".join(errors))

        self.logger.info("✅ Partial deletion verification completed")


class VerifyRemainingEntitiesStep(TestStep):
    """Verify that remaining entities are still present in vector database."""

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
                    f"Entity {self._display_name(entity)} was incorrectly removed from vector database"
                )
            else:
                self.logger.info(
                    f"✅ Entity {self._display_name(entity)} confirmed still present in vector database"
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
    """Verify that all test entities are completely removed from vector database."""

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

            # Always use 1000 limit for comprehensive search (expecting it to be absent/deleted)
            present = await _token_present_in_collection(
                client, self.context.collection_readable_id, expected_token, 1000, expect_present=False
            )

            if present:
                # Let's see what was found
                self.logger.warning(
                    f"⚠️ Entity {self._display_name(entity)} still found with token: {expected_token}"
                )
                # Do a more detailed search to see what's in vector database
                try:
                    results = await _search_collection_async(
                        client, self.context.collection_readable_id, expected_token, 5
                    )
                    for r in results[:2]:  # Show first 2 results
                        # New structure: id and name are at top level
                        self.logger.info(
                            f"   Found in vector DB: id={r.get('id')}, name={r.get('name')}"
                        )
                except Exception as e:
                    self.logger.debug(f"Could not get detailed results: {e}")

            return entity, (not present)

        results = await asyncio.gather(*[check_deleted(e) for e in all_test_entities])

        errors = []
        for entity, is_removed in results:
            if not is_removed:
                errors.append(
                    f"Entity {self._display_name(entity)} still exists in vector database after complete deletion"
                )
            else:
                self.logger.info(
                    f"✅ Entity {self._display_name(entity)} confirmed removed from vector database"
                )

        if errors:
            raise Exception("; ".join(errors))

        # Always use 1000 limit for comprehensive search
        collection_empty = await self._verify_collection_empty_of_test_data(
            client, 1000
        )
        if not collection_empty:
            self.logger.warning(
                "⚠️ Collection still contains some data (may be metadata entities)"
            )
        else:
            self.logger.info("✅ Collection confirmed empty of test data")

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
                        # New structure: name and score are at top level
                        score = r.get("score")
                        self.logger.info(
                            f"   - {r.get('name', 'Unknown')} (score: {score})"
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
            # Only clean up collections that belong to this specific test
            # This prevents race conditions where tests delete each other's collections
            if (
                hasattr(self.context, "collection_readable_id")
                and self.context.collection_readable_id
            ):
                self.logger.info(
                    f"🔍 Cleaning up current test collection: {self.context.collection_readable_id}"
                )

                try:
                    response = http_utils.http_delete(
                        f"/collections/{self.context.collection_readable_id}"
                    )
                    if response.status_code in [200, 204]:
                        cleanup_stats["collections_deleted"] += 1
                        self.logger.info(
                            f"✅ Deleted collection: {self.context.collection_readable_id}"
                        )
                    elif response.status_code == 404:
                        self.logger.info("ℹ️  Collection already deleted")
                    else:
                        cleanup_stats["errors"] += 1
                        self.logger.warning(
                            f"⚠️ Failed to delete collection {self.context.collection_readable_id}: {response.status_code}"
                        )
                except Exception as e:
                    cleanup_stats["errors"] += 1
                    self.logger.warning(
                        f"⚠️ Failed to delete collection {self.context.collection_readable_id}: {e}"
                    )
            else:
                self.logger.info("ℹ️  No collection to clean up for this test")

            # Log cleanup summary
            self.logger.info(
                f"🧹 Collection cleanup completed: {cleanup_stats['collections_deleted']} collections deleted, "
                f"{cleanup_stats['errors']} errors"
            )

        except Exception as e:
            self.logger.error(f"❌ Error during collection cleanup: {e}")
            # Don't re-raise - cleanup should be best-effort


class VerifyRawDataStep(TestStep):
    """Verify raw data was captured to local storage (local backend only).

    This step checks that the raw data capture system stored entity data
    during sync. It automatically skips when running against a remote
    Airweave backend since local filesystem access is required.
    """

    def _is_local_backend(self) -> bool:
        """Check if pointing at a local Airweave backend."""
        url = os.getenv("AIRWEAVE_API_URL", "http://localhost:8001").lower()
        return any(x in url for x in ["localhost", "127.0.0.1", "0.0.0.0"])

    async def execute(self) -> None:
        """Verify raw data files exist for the current sync."""
        self.logger.info("=" * 80)
        self.logger.info("📦 RAW DATA VERIFICATION: Checking local storage capture")
        self.logger.info("=" * 80)

        # Skip if not running locally
        if not self._is_local_backend():
            self.logger.info("⏭️ Skipping raw data verification (remote backend)")
            self.logger.info("   Raw data capture verification requires local filesystem access")
            return

        # Get sync_id from context
        sync_id = self.context.sync_id
        if not sync_id:
            self.logger.warning("⚠️ No sync_id found in context, skipping raw data verification")
            return

        self.logger.info(f"🔍 Verifying raw data for sync: {sync_id}")

        # Import Path here to avoid top-level import issues
        from pathlib import Path

        # Determine storage path - check common locations
        storage_path = os.getenv("STORAGE_PATH")
        if storage_path:
            base_path = Path(storage_path)
        else:
            # Try common local development paths (local_storage lives at repo root)
            candidates = [
                Path("local_storage"),
                Path("/app/local_storage"),
            ]
            base_path = None
            for candidate in candidates:
                if candidate.exists():
                    base_path = candidate
                    break

            if not base_path:
                self.logger.warning("⚠️ Could not find local_storage directory, skipping verification")
                return

        raw_path = base_path / "raw" / sync_id
        self.logger.info(f"📂 Checking raw data path: {raw_path}")

        errors = []

        # Check manifest exists
        manifest = raw_path / "manifest.json"
        if not manifest.exists():
            errors.append(f"Missing manifest.json at {manifest}")
        else:
            self.logger.info("✅ Found manifest.json")

        # Check entities directory has files
        entities_dir = raw_path / "entities"
        if not entities_dir.exists():
            errors.append(f"Missing entities directory at {entities_dir}")
        else:
            entity_files = list(entities_dir.glob("*.json"))
            if not entity_files:
                errors.append(f"No entity JSON files in {entities_dir}")
            else:
                self.logger.info(f"✅ Found {len(entity_files)} entity file(s)")

        # Check files directory (optional - only for file-based connectors)
        files_dir = raw_path / "files"
        if files_dir.exists():
            file_count = len(list(files_dir.iterdir()))
            if file_count > 0:
                self.logger.info(f"✅ Found {file_count} raw file(s) in files directory")
            else:
                self.logger.info("ℹ️ Files directory exists but is empty")
        else:
            self.logger.info("ℹ️ No files directory (normal for non-file connectors)")

        # Report results
        self.logger.info("=" * 80)
        if errors:
            self.logger.error(f"❌ RAW DATA VERIFICATION FAILED")
            for error in errors:
                self.logger.error(f"   • {error}")
            self.logger.info("=" * 80)
            raise Exception("; ".join(errors))
        else:
            entity_count = len(list(entities_dir.glob("*.json"))) if entities_dir.exists() else 0
            self.logger.info(f"✅ RAW DATA VERIFICATION PASSED")
            self.logger.info(f"📊 Summary: {entity_count} entities captured to {raw_path}")
            self.logger.info("=" * 80)


class TestStepFactory:
    """Factory for creating test steps."""

    _steps = {
        "cleanup": CleanupStep,
        "collection_cleanup": CollectionCleanupStep,
        "create": CreateStep,
        "sync": SyncStep,
        "force_full_sync": SyncStep,  # Use same class with force_full_sync=True
        "verify": VerifyStep,
        "verify_raw_data": VerifyRawDataStep,
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

        step_class = self._steps[step_name]

        # Special handling for force_full_sync step
        if step_name == "force_full_sync":
            return step_class(config, context, force_full_sync=True)

        return step_class(config, context)
