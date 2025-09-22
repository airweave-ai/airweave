"""Test step implementations with parallelized verification and robust sync handling."""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from monke.core.config import TestConfig
from monke.utils.logging import get_logger


class TestStep(ABC):
    """Abstract base class for test steps."""

    def __init__(self, config: TestConfig):
        """Initialize the test step."""
        self.config = config
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
    async def execute(self):
        """Execute the test step."""
        raise NotImplementedError


class CreateStep(TestStep):
    """Create test entities step."""

    async def execute(self):
        """Create test entities via the connector."""
        self.logger.info("🥁 Creating test entities")

        bongo = self._get_bongo()
        entities = await bongo.create_entities()

        # Optional post-create delay to allow upstream APIs to propagate data
        delay_seconds = 0
        try:
            delay_override = (
                self.config.connector.config_fields.get("post_create_sleep_seconds")
                if hasattr(self.config, "connector")
                and hasattr(self.config.connector, "config_fields")
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
        self.config._created_entities = entities
        if hasattr(self.config, "_bongo"):
            self.config._bongo.created_entities = entities

    def _get_bongo(self):
        return getattr(self.config, "_bongo", None)


class SyncStep(TestStep):
    """Sync data to Airweave step."""

    async def execute(self):
        """Trigger sync and wait for completion."""
        self.logger.info("🔄 Syncing data to Airweave")
        client = self._get_airweave_client()

        # If a job is already running, wait for it, BUT ALWAYS launch our own sync afterwards
        active_job_id = self._find_active_job_id(client)
        if active_job_id:
            self.logger.info(
                f"🟡 A sync is already in progress (job {active_job_id}); waiting for it to complete."
            )
            await self._wait_for_sync_completion(client, target_job_id=active_job_id)
            self.logger.info(
                "🧭 Previous sync finished; launching a fresh sync to capture recent changes"
            )

        # Try to start a new sync. If the server says one is already running, wait for that one,
        # then START OUR OWN sync and wait for it too.
        target_job_id = None
        try:
            run_resp = client.source_connections.run(self.config._source_connection_id)
            target_job_id = (
                getattr(run_resp, "id", None)
                or getattr(run_resp, "job_id", None)
                or getattr(run_resp, "sync_job_id", None)
            )
        except Exception as e:
            msg = str(e).lower()
            if "already has a running job" in msg or "already running" in msg:
                self.logger.warning("⚠️ Sync already running; discovering and waiting for that job.")
                active_job_id = self._find_active_job_id(client) or self._latest_job_id(client)
                if not active_job_id:
                    # Last resort: brief wait then re-check
                    await asyncio.sleep(2.0)
                    active_job_id = self._find_active_job_id(client) or self._latest_job_id(client)
                if not active_job_id:
                    raise  # nothing to wait on; re-raise original error
                await self._wait_for_sync_completion(client, target_job_id=active_job_id)

                # IMPORTANT: after the previous job completes, start *our* job
                run_resp = client.source_connections.run(self.config._source_connection_id)
                target_job_id = (
                    getattr(run_resp, "id", None)
                    or getattr(run_resp, "job_id", None)
                    or getattr(run_resp, "sync_job_id", None)
                )
            else:
                raise  # unknown error

        await self._wait_for_sync_completion(client, target_job_id=target_job_id)
        self.logger.info("✅ Sync completed")

    def _get_airweave_client(self):
        return getattr(self.config, "_airweave_client", None)

    def _jobs_sorted(self, client):
        jobs = client.source_connections.list_jobs(self.config._source_connection_id) or []

        def _ts(j):
            return getattr(j, "started_at", None) or getattr(j, "created_at", None) or 0

        return sorted(jobs, key=_ts, reverse=True)

    def _find_active_job_id(self, client) -> Optional[str]:
        ACTIVE = {"created", "pending", "in_progress", "running", "queued"}
        try:
            for j in self._jobs_sorted(client):
                status = (getattr(j, "status", "") or "").lower()
                if status in ACTIVE:
                    return (
                        str(getattr(j, "id", ""))  # type: ignore
                        or str(getattr(j, "job_id", ""))  # type: ignore
                        or str(getattr(j, "sync_job_id", ""))  # type: ignore
                    )
        except Exception:
            pass
        return None

    def _latest_job_id(self, client) -> Optional[str]:
        try:
            sc = client.source_connections.get(self.config._source_connection_id)
            latest = getattr(sc, "latest_sync_job_id", None)
            if latest:
                return str(latest)
        except Exception:
            pass

        # Fallback to the newest job in the list
        try:
            jobs_sorted = self._jobs_sorted(client)
            if jobs_sorted:
                j = jobs_sorted[0]
                return (
                    str(getattr(j, "id", ""))  # type: ignore
                    or str(getattr(j, "job_id", ""))  # type: ignore
                    or str(getattr(j, "sync_job_id", ""))  # type: ignore
                )
        except Exception:
            pass
        return None

    async def _wait_for_sync_completion(
        self,
        client,
        target_job_id: Optional[str],
        timeout_seconds: int = 300,
    ):
        """Wait for the started sync job (or current active one) to complete."""
        self.logger.info("⏳ Waiting for sync to complete...")

        def _job_status_fields(job) -> Dict[str, Any]:
            status = (getattr(job, "status", "") or "").lower()
            completed_at = getattr(job, "completed_at", None)
            failed_at = getattr(job, "failed_at", None)
            
            is_complete = status == "completed" and completed_at is not None
            
            is_failed = status == "failed" or failed_at is not None
            
            return {
                "status": status,
                "is_complete": is_complete,
                "is_failed": is_failed,
                "error": getattr(job, "error", None),
                "created_at": getattr(job, "created_at", None),
                "started_at": getattr(job, "started_at", None),
                "completed_at": completed_at,
                "failed_at": failed_at,
                "id": str(getattr(job, "id", ""))
                or str(getattr(job, "job_id", ""))
                or str(getattr(job, "sync_job_id", "")),
            }

        ACTIVE = {"created", "pending", "in_progress", "running", "queued"}

        # If no job id provided, try to discover an active one first.
        if not target_job_id:
            target_job_id = self._find_active_job_id(client)

        # If still none, fall back to observing latest_sync_job_id
        if not target_job_id:
            self.logger.info("ℹ️ No job id available; discovering via latest_sync_job_id …")
            start = time.monotonic()
            prev_latest = getattr(self.config, "_last_sync_job_id", None)

            while time.monotonic() - start < timeout_seconds:
                sc = client.source_connections.get(self.config._source_connection_id)
                latest = getattr(sc, "latest_sync_job_id", None)
                if latest and latest != prev_latest:
                    target_job_id = latest
                    self.logger.info(f"🆔 Detected sync job id: {target_job_id}")
                    break
                await asyncio.sleep(2.0)

            if not target_job_id:
                raise RuntimeError("Couldn’t obtain a sync job id to wait on.")

        start = time.monotonic()
        while time.monotonic() - start < timeout_seconds:
            # Prefer a direct job lookup when available
            job = None
            try:
                if hasattr(client.source_connections, "get_job"):
                    job = client.source_connections.get_job(
                        source_connection_id=self.config._source_connection_id,
                        job_id=target_job_id,
                    )
                else:
                    jobs_sorted = self._jobs_sorted(client)
                    for j in jobs_sorted:
                        jid = (
                            str(getattr(j, "id", ""))  # type: ignore
                            or str(getattr(j, "job_id", ""))  # type: ignore
                            or str(getattr(j, "sync_job_id", ""))  # type: ignore
                        )
                        if jid == str(target_job_id):
                            job = j
                            break
            except Exception as e:
                self.logger.warning(f"⚠️ Error fetching job status: {e}")
                job = None

            if not job:
                await asyncio.sleep(2.0)
                continue

            fields = _job_status_fields(job)
            self.logger.info(
                f"🔍 Job {target_job_id} status={fields['status']}, complete={fields['is_complete']}"
            )

            if fields["is_failed"] or fields["status"] == "failed":
                raise RuntimeError(f"Sync failed: {fields['error'] or 'unknown error'}")

            # Done when job is complete (calculated from status + completed_at)
            if fields["is_complete"]:
                self.config._last_sync_job_id = str(target_job_id)  # cache for next time
                self.logger.info(
                    f"✅ Sync completed successfully (status={fields['status']}, completed_at={fields['completed_at']})"
                )
                return

            if fields["status"] in ACTIVE or not fields["status"]:
                await asyncio.sleep(2.0)
                continue

            # Unexpected state, keep polling briefly
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
    client, readable_id: str, query: str, limit: int
) -> List[Dict[str, Any]]:
    """
    Run a (likely synchronous) Airweave SDK search in a worker thread so we can do many in parallel.
    """

    def _run():
        return client.collections.search(
            readable_id=readable_id,
            query=query,
            limit=limit,
        )

    resp = await asyncio.to_thread(_run)
    return _safe_results_from_search_response(resp)


async def _token_present_in_collection(client, readable_id: str, token: str, limit: int) -> bool:
    """
    Check if `token` appears in any result payload (case-insensitive).
    """
    try:
        results = await _search_collection_async(client, readable_id, token, limit)
        token_lower = token.lower()
        for r in results:
            payload = r.get("payload", {})
            if payload and token_lower in str(payload).lower():
                return True
        return False
    except Exception:
        return False


def _search_limit_from_config(config: TestConfig, default: int = 50) -> int:
    try:
        return int(config.verification_config.get("search_limit", default))
    except Exception:
        return default


# ---------- Verification steps (parallelized) ----------


class VerifyStep(TestStep):
    """Verify data in Qdrant step."""

    async def execute(self):
        self.logger.info("🔍 Verifying entities in Qdrant")
        client = self._get_airweave_client()
        limit = _search_limit_from_config(self.config)

        async def verify_one(entity: Dict[str, Any]):
            expected_token = entity.get("token")
            if not expected_token:
                self.logger.warning("⚠️ No token found in entity, falling back to filename")
                expected_token = (entity.get("path") or "").split("/")[-1]

            ok = await _token_present_in_collection(
                client, self.config._collection_readable_id, expected_token, limit
            )
            return entity, ok

        # Retry support + optional one-time rescue resync
        attempts = int(self.config.verification_config.get("retries", 5))
        backoff = float(self.config.verification_config.get("retry_backoff_seconds", 1.0))
        resync_on_miss = bool(self.config.verification_config.get("resync_on_miss", True))

        resync_lock = asyncio.Lock()
        resync_triggered = False

        async def verify_with_retries(e: Dict[str, Any]):
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
                        await SyncStep(self.config).execute()
                # Final check after resync
                return await verify_one(e)

            return e, False

        results = await asyncio.gather(
            *[verify_with_retries(e) for e in self.config._created_entities]
        )

        errors = []
        for entity, ok in results:
            if not ok:
                errors.append(f"Entity {self._display_name(entity)} not found in Qdrant")
            else:
                self.logger.info(f"✅ Entity {self._display_name(entity)} verified in Qdrant")

        if errors:
            raise Exception("; ".join(errors))

        self.logger.info("✅ All entities verified in Qdrant")

    def _get_airweave_client(self):
        return getattr(self.config, "_airweave_client", None)


class UpdateStep(TestStep):
    """Update test entities step."""

    async def execute(self):
        self.logger.info("📝 Updating test entities")
        bongo = self._get_bongo()
        updated_entities = await bongo.update_entities()
        self.logger.info(f"✅ Updated {len(updated_entities)} test entities")
        self.config._updated_entities = updated_entities

    def _get_bongo(self):
        return getattr(self.config, "_bongo", None)


class PartialDeleteStep(TestStep):
    """Partial deletion step - delete subset of entities based on test size."""

    async def execute(self):
        self.logger.info("🗑️ Executing partial deletion")
        bongo = self._get_bongo()

        deletion_count = self._calculate_partial_deletion_count()
        entities_to_delete = self.config._created_entities[:deletion_count]
        entities_to_keep = self.config._created_entities[deletion_count:]

        self.logger.info(
            f"🗑️ Deleting {len(entities_to_delete)} entities: "
            f"{[self._display_name(e) for e in entities_to_delete]}"
        )
        self.logger.info(
            f"💾 Keeping {len(entities_to_keep)} entities: "
            f"{[self._display_name(e) for e in entities_to_keep]}"
        )

        deleted_paths = await bongo.delete_specific_entities(entities_to_delete)

        self.config._partially_deleted_entities = entities_to_delete
        self.config._remaining_entities = entities_to_keep

        self.logger.info(f"✅ Partial deletion completed: {len(deleted_paths)} entities deleted")

    def _get_bongo(self):
        return getattr(self.config, "_bongo", None)

    def _calculate_partial_deletion_count(self) -> int:
        return self.config.deletion.partial_delete_count


class VerifyPartialDeletionStep(TestStep):
    """Verify that partially deleted entities are removed from Qdrant."""

    async def execute(self):
        self.logger.info("🔍 Verifying partial deletion")

        if not self.config.deletion.verify_partial_deletion:
            self.logger.info("⏭️ Skipping partial deletion verification (disabled in config)")
            return

        client = self._get_airweave_client()
        limit = _search_limit_from_config(self.config)

        self.logger.info("🔍 Expecting these entities to be deleted:")
        for entity in self.config._partially_deleted_entities:
            self.logger.info(
                f"   - {self._display_name(entity)} (token: {entity.get('token', 'N/A')})"
            )

        async def check_deleted(entity: Dict[str, Any]):
            expected_token = entity.get("token") or str(
                entity.get("id") or entity.get("gid") or entity.get("name", "")
            )
            if not expected_token:
                return entity, False
            present = await _token_present_in_collection(
                client, self.config._collection_readable_id, expected_token, limit
            )
            return entity, (not present)

        results = await asyncio.gather(
            *[check_deleted(e) for e in self.config._partially_deleted_entities]
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

    def _get_airweave_client(self):
        return getattr(self.config, "_airweave_client", None)


class VerifyRemainingEntitiesStep(TestStep):
    """Verify that remaining entities are still present in Qdrant."""

    async def execute(self):
        self.logger.info("🔍 Verifying remaining entities are still present")

        if not self.config.deletion.verify_remaining_entities:
            self.logger.info("⏭️ Skipping remaining entities verification (disabled in config)")
            return

        client = self._get_airweave_client()
        limit = _search_limit_from_config(self.config)

        async def check_present(entity: Dict[str, Any]):
            expected_token = entity.get("token") or (
                (entity.get("path", "").split("/")[-1])
                if entity.get("path")
                else str(entity.get("id", ""))
            )
            if not expected_token:
                return entity, False
            present = await _token_present_in_collection(
                client, self.config._collection_readable_id, expected_token, limit
            )
            return entity, present

        results = await asyncio.gather(*[check_present(e) for e in self.config._remaining_entities])

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

    def _get_airweave_client(self):
        return getattr(self.config, "_airweave_client", None)


class CompleteDeleteStep(TestStep):
    """Complete deletion step - delete all remaining entities."""

    async def execute(self):
        self.logger.info("🗑️ Executing complete deletion")

        bongo = self._get_bongo()

        remaining_entities = self.config._remaining_entities
        if not remaining_entities:
            self.logger.info("ℹ️ No remaining entities to delete")
            return

        self.logger.info(f"🗑️ Deleting remaining {len(remaining_entities)} entities")

        deleted_paths = await bongo.delete_specific_entities(remaining_entities)

        self.logger.info(f"✅ Complete deletion completed: {len(deleted_paths)} entities deleted")

    def _get_bongo(self):
        return getattr(self.config, "_bongo", None)


class VerifyCompleteDeletionStep(TestStep):
    """Verify that all test entities are completely removed from Qdrant."""

    async def execute(self):
        self.logger.info("🔍 Verifying complete deletion")

        if not self.config.deletion.verify_complete_deletion:
            self.logger.info("⏭️ Skipping complete deletion verification (disabled in config)")
            return

        client = self._get_airweave_client()
        limit = _search_limit_from_config(self.config)

        all_test_entities = (
            self.config._partially_deleted_entities + self.config._remaining_entities
        )

        async def check_deleted(entity: Dict[str, Any]):
            expected_token = entity.get("token") or (
                (entity.get("path", "").split("/")[-1])
                if entity.get("path")
                else str(entity.get("id", ""))
            )
            if not expected_token:
                return entity, False
            present = await _token_present_in_collection(
                client, self.config._collection_readable_id, expected_token, limit
            )
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

        collection_empty = await self._verify_collection_empty_of_test_data(client, limit)
        if not collection_empty:
            self.logger.warning(
                "⚠️ Qdrant collection still contains some data (may be metadata entities)"
            )
        else:
            self.logger.info("✅ Qdrant collection confirmed empty of test data")

        self.logger.info("✅ Complete deletion verification completed")

    def _get_airweave_client(self):
        return getattr(self.config, "_airweave_client", None)

    async def _verify_collection_empty_of_test_data(self, client, limit: int) -> bool:
        try:
            test_patterns = ["monke-test", "Monke Test"]

            async def search_one(pattern: str):
                try:
                    results = await _search_collection_async(
                        client,
                        self.config._collection_readable_id,
                        pattern,
                        limit=min(limit, 25),
                    )
                    return pattern, results
                except Exception:
                    return pattern, []

            pattern_results = await asyncio.gather(*[search_one(p) for p in test_patterns])

            total = 0
            for pattern, results in pattern_results:
                count = len(results)
                total += count
                if count:
                    self.logger.info(f"🔍 Found {count} results for pattern '{pattern}'")
                    for r in results[:3]:
                        payload = r.get("payload", {})
                        score = r.get("score")
                        self.logger.info(f"   - {payload.get('name', 'Unknown')} (score: {score})")

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

    async def execute(self):
        """Clean up all test data from the source workspace."""
        self.logger.info("🧹 Cleaning up source workspace")
        bongo = self._get_bongo()

        try:
            await bongo.cleanup()
            self.logger.info("✅ Source workspace cleanup completed")
        except Exception as e:
            # Don't fail the test if cleanup fails, just log the warning
            self.logger.warning(f"⚠️ Cleanup encountered issues: {e}")

    def _get_bongo(self):
        return getattr(self.config, "_bongo", None)


class CollectionCleanupStep(TestStep):
    """Collection cleanup step - clean up old test collections from Airweave."""

    async def execute(self):
        """Clean up old test collections from Airweave."""
        self.logger.info("🧹 Cleaning up old test collections")
        client = self._get_airweave_client()

        if not client:
            self.logger.warning("⚠️ No Airweave client available for collection cleanup")
            return

        cleanup_stats = {"collections_deleted": 0, "errors": 0}

        try:
            # Find all test collections
            test_collections = await self._find_test_collections(client)

            if test_collections:
                self.logger.info(f"🔍 Found {len(test_collections)} test collections to clean up")

                for collection in test_collections:
                    try:
                        client.collections.delete(collection["readable_id"])
                        cleanup_stats["collections_deleted"] += 1
                        self.logger.info(
                            f"✅ Deleted collection: {collection['name']} ({collection['readable_id']})"
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

    def _get_airweave_client(self):
        return getattr(self.config, "_airweave_client", None)

    async def _find_test_collections(self, client) -> List[Dict[str, Any]]:
        """Find all test collections that should be cleaned up."""
        test_collections = []

        try:
            # Get all collections
            collections = client.collections.list()

            # Convert to list if it's a generator or iterator
            if hasattr(collections, "__iter__") and not isinstance(collections, list):
                collections = list(collections)

            for collection in collections:
                # Convert to dict if it's a Pydantic model
                if hasattr(collection, "model_dump"):
                    collection_data = collection.model_dump()
                elif hasattr(collection, "dict"):
                    collection_data = collection.dict()
                else:
                    collection_data = (
                        dict(collection) if hasattr(collection, "__dict__") else collection
                    )

                name = collection_data.get("name", "")
                readable_id = collection_data.get("readable_id", "")

                # Check if this looks like a test collection
                is_test_collection = (
                    name.lower().startswith("monke-")
                    or "test" in name.lower()
                    and ("collection" in name.lower() or "monke" in name.lower())
                    or readable_id.startswith("monke-")
                )

                if is_test_collection:
                    test_collections.append(collection_data)

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

    def create_step(self, step_name: str, config: TestConfig) -> TestStep:
        if step_name not in self._steps:
            raise ValueError(f"Unknown test step: {step_name}")
        return self._steps[step_name](config)
